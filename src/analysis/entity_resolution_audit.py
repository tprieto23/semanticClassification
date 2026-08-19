"""Auditoría en seco de la resolución de entidades v2.

Ejecuta el algoritmo contra PostgreSQL dentro de una transacción que siempre
se revierte. Compara las identidades y la red de coocurrencia actuales con las
que produciría el rediseño, sin reemplazar menciones ni persistir canónicos o
alias nuevos.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable, Sequence

from sqlalchemy import func, select

from src.analysis.cooccurrence import (
    CooccurrenceResult,
    MentionRecord,
    build_sentence_cooccurrence,
    load_db_mentions,
    load_ner_json,
    validate_json_against_db,
)
from src.models.canonical_entities import CanonicalEntity
from src.models.canonical_entity_aliases import CanonicalEntityAlias
from src.models.database import SessionLocal
from src.models.documents import Document  # noqa: F401 - configura el mapper
from src.models.entities import Entity
from src.services.fuzzy_matching import (
    RESOLUTION_VERSION,
    asociar_entidades_canonicas,
    normalizar_nombre,
)


def _signature(
    *,
    category: str,
    text: str,
    start: int,
    end: int,
    sentence_id: str,
    context: str | None,
    ambiguity: str | None,
) -> tuple[Any, ...]:
    return (category, text, start, end, sentence_id, context, ambiguity)


def _json_signature(entity: dict[str, Any]) -> tuple[Any, ...]:
    return _signature(
        category=entity["category"],
        text=entity["text"],
        start=entity["start"],
        end=entity["end"],
        sentence_id=entity["sentence_id"],
        context=entity.get("context"),
        ambiguity=entity.get("ambiguity"),
    )


def _mention_signature(mention: MentionRecord) -> tuple[Any, ...]:
    return _signature(
        category=mention.category,
        text=mention.text,
        start=mention.start,
        end=mention.end,
        sentence_id=mention.sentence_id,
        context=mention.context,
        ambiguity=mention.ambiguity,
    )


def _database_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "canonical_entities": db.scalar(
                select(func.count()).select_from(CanonicalEntity)
            )
            or 0,
            "canonical_entity_aliases": db.scalar(
                select(func.count()).select_from(CanonicalEntityAlias)
            )
            or 0,
            "entities": db.scalar(select(func.count()).select_from(Entity)) or 0,
        }


def _resolve_dry_run(
    document_id: str, entities: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    db = SessionLocal()
    try:
        resolved, statistics = asociar_entidades_canonicas(
            db, entities, document_id=document_id
        )
        # Materializa valores simples antes de expirar objetos ORM al rollback.
        materialized = [dict(entity) for entity in resolved]
        return materialized, statistics
    finally:
        db.rollback()
        db.close()


def _align_baseline(
    entities: Sequence[dict[str, Any]], baseline: Sequence[MentionRecord]
) -> list[MentionRecord]:
    mentions_by_signature: dict[tuple[Any, ...], deque[MentionRecord]] = defaultdict(
        deque
    )
    for mention in baseline:
        mentions_by_signature[_mention_signature(mention)].append(mention)

    aligned: list[MentionRecord] = []
    for entity in entities:
        signature = _json_signature(entity)
        if not mentions_by_signature[signature]:
            raise ValueError("No fue posible alinear una mención JSON con PostgreSQL")
        aligned.append(mentions_by_signature[signature].popleft())
    return aligned


def _to_mention_records(
    document_id: str, resolved: Sequence[dict[str, Any]]
) -> list[MentionRecord]:
    return [
        MentionRecord(
            mention_id=None,
            document_id=document_id,
            sentence_id=entity["sentence_id"],
            canonical_id=str(entity["canonical_id"]),
            canonical_name=entity["canonical_name"],
            category=entity["category"],
            text=entity["text"],
            start=entity["start"],
            end=entity["end"],
            context=entity.get("context"),
            ambiguity=entity.get("ambiguity"),
        )
        for entity in resolved
    ]


def _network_summary(result: CooccurrenceResult) -> dict[str, Any]:
    recurring_edges = {
        edge: weight for edge, weight in result.edge_weights.items() if weight >= 3
    }
    recurring_nodes = {index for edge in recurring_edges for index in edge}
    return {
        "nodes": len(result.nodes),
        "edges": len(result.edge_weights),
        "total_edge_weight": sum(result.edge_weights.values()),
        "max_edge_weight": max(result.edge_weights.values(), default=0),
        "g3_nodes": len(recurring_nodes),
        "g3_edges": len(recurring_edges),
        "g3_total_edge_weight": sum(recurring_edges.values()),
    }


def _node_metrics(result: CooccurrenceResult) -> dict[str, dict[str, Any]]:
    neighbors: dict[int, set[int]] = defaultdict(set)
    recurring_neighbors: dict[int, set[int]] = defaultdict(set)
    strength: Counter[int] = Counter()
    recurring_strength: Counter[int] = Counter()
    for (source, target), weight in result.edge_weights.items():
        neighbors[source].add(target)
        neighbors[target].add(source)
        strength[source] += weight
        strength[target] += weight
        if weight >= 3:
            recurring_neighbors[source].add(target)
            recurring_neighbors[target].add(source)
            recurring_strength[source] += weight
            recurring_strength[target] += weight

    return {
        node.canonical_id: {
            "canonical_id": node.canonical_id,
            "canonical_name": node.canonical_name,
            "category": node.category,
            "mention_count": node.mention_count,
            "sentence_count": node.sentence_count,
            "degree_g1": len(neighbors[node.matrix_index]),
            "strength_g1": strength[node.matrix_index],
            "degree_g3": len(recurring_neighbors[node.matrix_index]),
            "strength_g3": recurring_strength[node.matrix_index],
        }
        for node in result.nodes
    }


def _decision_rows(
    entities: Sequence[dict[str, Any]],
    baseline: Sequence[MentionRecord],
    resolved: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, old, new in zip(entities, baseline, resolved, strict=True):
        details = new["resolution_details"]
        rows.append(
            {
                "sentence_id": source["sentence_id"],
                "start": source["start"],
                "end": source["end"],
                "category": source["category"],
                "text": source["text"],
                "old_canonical_id": old.canonical_id,
                "old_canonical_name": old.canonical_name,
                "new_canonical_id": str(new["canonical_id"]),
                "new_canonical_name": new["canonical_name"],
                "changed_canonical_id": old.canonical_id != str(new["canonical_id"]),
                "match_type": new["match_type"],
                "match_score": new["match_score"],
                "second_match_score": new["second_match_score"],
                "preferred_name": details["preferred_name"],
                "strategy": details["strategy"],
                "rule": details.get("rule", ""),
                "reason": details["reason"],
                "base_match_type": details["base_match_type"],
            }
        )
    return rows


def _edge_rows(
    result: CooccurrenceResult, *, minimum_weight: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (source_index, target_index), weight in result.edge_weights.items():
        if weight < minimum_weight:
            continue
        source = result.nodes[source_index]
        target = result.nodes[target_index]
        rows.append(
            {
                "source_canonical_id": source.canonical_id,
                "source_name": source.canonical_name,
                "source_category": source.category,
                "target_canonical_id": target.canonical_id,
                "target_name": target.canonical_name,
                "target_category": target.category,
                "sentence_count": weight,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -row["sentence_count"],
            row["source_name"].casefold(),
            row["target_name"].casefold(),
        ),
    )


def _convergences(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["new_canonical_id"]].append(row)

    convergence_rows: list[dict[str, Any]] = []
    for new_id, group in grouped.items():
        old_ids = {row["old_canonical_id"] for row in group}
        if len(old_ids) < 2:
            continue
        convergence_rows.append(
            {
                "new_canonical_id": new_id,
                "new_canonical_name": group[0]["new_canonical_name"],
                "category": group[0]["category"],
                "mention_count": len(group),
                "old_canonical_count": len(old_ids),
                "old_canonical_ids": " | ".join(sorted(old_ids)),
                "old_canonical_names": " | ".join(
                    sorted(
                        {row["old_canonical_name"] for row in group}, key=str.casefold
                    )
                ),
                "observed_texts": " | ".join(
                    sorted({row["text"] for row in group}, key=str.casefold)
                ),
                "methods": " | ".join(sorted({row["match_type"] for row in group})),
            }
        )
    return sorted(
        convergence_rows,
        key=lambda row: (-row["mention_count"], row["new_canonical_name"].casefold()),
    )


def _splits(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["old_canonical_id"]].append(row)

    split_rows: list[dict[str, Any]] = []
    for old_id, group in grouped.items():
        new_ids = {row["new_canonical_id"] for row in group}
        if len(new_ids) < 2:
            continue
        split_rows.append(
            {
                "old_canonical_id": old_id,
                "old_canonical_name": group[0]["old_canonical_name"],
                "category": group[0]["category"],
                "mention_count": len(group),
                "new_canonical_count": len(new_ids),
                "new_canonical_ids": " | ".join(sorted(new_ids)),
                "new_canonical_names": " | ".join(
                    sorted(
                        {row["new_canonical_name"] for row in group}, key=str.casefold
                    )
                ),
                "observed_texts": " | ".join(
                    sorted({row["text"] for row in group}, key=str.casefold)
                ),
            }
        )
    return sorted(
        split_rows,
        key=lambda row: (-row["mention_count"], row["old_canonical_name"].casefold()),
    )


def _created_canonicals(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["base_match_type"] == "new":
            grouped[row["new_canonical_id"]].append(row)

    created = [
        {
            "new_canonical_id": canonical_id,
            "new_canonical_name": group[0]["new_canonical_name"],
            "category": group[0]["category"],
            "mention_count": len(group),
            "observed_texts": " | ".join(
                sorted({row["text"] for row in group}, key=str.casefold)
            ),
            "strategy": group[0]["strategy"],
            "reason": group[0]["reason"],
        }
        for canonical_id, group in grouped.items()
    ]
    return sorted(
        created,
        key=lambda row: (-row["mention_count"], row["new_canonical_name"].casefold()),
    )


def _focus_report(
    rows: Sequence[dict[str, Any]],
    baseline_metrics: dict[str, dict[str, Any]],
    redesigned_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    focus_predicates = {
        "griselda": lambda text: normalizar_nombre(text).startswith("griselda"),
        "minero": lambda text: normalizar_nombre(text) in {"minero", "mineros"},
        "minera": lambda text: normalizar_nombre(text) in {"minera", "mineras"},
    }
    report: dict[str, Any] = {}
    for name, predicate in focus_predicates.items():
        matching = [row for row in rows if predicate(row["text"])]
        old_ids = sorted({row["old_canonical_id"] for row in matching})
        new_ids = sorted({row["new_canonical_id"] for row in matching})
        report[name] = {
            "mention_count": len(matching),
            "observed_texts": sorted(
                {row["text"] for row in matching}, key=str.casefold
            ),
            "before": [baseline_metrics[item] for item in old_ids],
            "after": [redesigned_metrics[item] for item in new_ids],
        }
    return report


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_filtered_decisions(
    output_dir: Path, rows: Sequence[dict[str, Any]], methods: Iterable[str]
) -> None:
    for method in methods:
        _write_csv(
            output_dir / f"decisions_{method}.csv",
            [row for row in rows if row["match_type"] == method],
        )


def run_audit(ner_json: Path, output_dir: Path) -> dict[str, Any]:
    document_id, entities = load_ner_json(ner_json)
    baseline_mentions = load_db_mentions(document_id)
    validate_json_against_db(entities, baseline_mentions)
    aligned_baseline = _align_baseline(entities, baseline_mentions)

    counts_before = _database_counts()
    resolved, statistics = _resolve_dry_run(document_id, entities)
    counts_after = _database_counts()

    redesigned_mentions = _to_mention_records(document_id, resolved)
    baseline_network = build_sentence_cooccurrence(aligned_baseline)
    redesigned_network = build_sentence_cooccurrence(redesigned_mentions)
    decision_rows = _decision_rows(entities, aligned_baseline, resolved)
    convergence_rows = _convergences(decision_rows)
    split_rows = _splits(decision_rows)
    created_rows = _created_canonicals(decision_rows)

    baseline_metrics = _node_metrics(baseline_network)
    redesigned_metrics = _node_metrics(redesigned_network)
    changed_mentions = sum(row["changed_canonical_id"] for row in decision_rows)
    created_ids = {row["new_canonical_id"] for row in created_rows}
    summary = {
        "mode": "dry_run_transaction_rolled_back",
        "resolution_version": RESOLUTION_VERSION,
        "document_id": document_id,
        "ner_json": str(ner_json),
        "mention_count": len(entities),
        "database_counts_before": counts_before,
        "database_counts_after": counts_after,
        "database_unchanged": counts_before == counts_after,
        "resolution_statistics": statistics,
        "changed_mentions": changed_mentions,
        "unchanged_mentions": len(entities) - changed_mentions,
        "created_canonical_groups": len(created_ids),
        "mentions_assigned_to_created_canonicals": sum(
            row["new_canonical_id"] in created_ids for row in decision_rows
        ),
        "convergence_count": len(convergence_rows),
        "split_count": len(split_rows),
        "network_before": _network_summary(baseline_network),
        "network_after": _network_summary(redesigned_network),
        "focus": _focus_report(decision_rows, baseline_metrics, redesigned_metrics),
        "largest_convergences": convergence_rows[:30],
        "created_canonicals": created_rows,
        "splits": split_rows,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "mention_decisions.csv", decision_rows)
    _write_csv(output_dir / "canonical_convergences.csv", convergence_rows)
    _write_csv(output_dir / "canonical_splits.csv", split_rows)
    _write_csv(output_dir / "created_canonicals.csv", created_rows)
    _write_csv(
        output_dir / "network_g3_before.csv",
        _edge_rows(baseline_network, minimum_weight=3),
    )
    _write_csv(
        output_dir / "network_g3_after.csv",
        _edge_rows(redesigned_network, minimum_weight=3),
    )
    _write_filtered_decisions(
        output_dir,
        decision_rows,
        ("morphology", "person_alias", "person_name", "fuzzy", "new"),
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ner-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    summary = run_audit(args.ner_json, args.output_dir)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "database_unchanged": summary["database_unchanged"],
                "changed_mentions": summary["changed_mentions"],
                "convergence_count": summary["convergence_count"],
                "split_count": summary["split_count"],
                "created_canonical_groups": summary["created_canonical_groups"],
                "network_before": summary["network_before"],
                "network_after": summary["network_after"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
