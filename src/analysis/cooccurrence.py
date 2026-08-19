"""Construcción reproducible de matrices de coocurrencia por oración.

La fuente de identidad de los nodos es ``canonical_entities`` y la unidad de
coocurrencia es el par ``(document_id, sentence_id)``. El módulo no modifica la
base de datos: consulta menciones ya canonicalizadas y exporta resultados
analíticos a archivos.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import UUID

CATEGORY_ORDER = ("CHAR", "PRAC", "INFRA", "GOV", "LOC")
CATEGORY_RANK = {category: index for index, category in enumerate(CATEGORY_ORDER)}
LAYER_BY_CATEGORY = {
    "CHAR": "CHAR",
    "PRAC": "L2",
    "INFRA": "L2",
    "GOV": "L2",
    "LOC": "LOC",
}

GROUP_CATEGORIES = {
    "CHAR": frozenset({"CHAR"}),
    "L2": frozenset({"PRAC", "INFRA", "GOV"}),
    "LOC": frozenset({"LOC"}),
    "PRAC": frozenset({"PRAC"}),
    "INFRA": frozenset({"INFRA"}),
    "GOV": frozenset({"GOV"}),
}

# Matrices de las tres macrocapas y descomposición interna de L2.
BLOCK_SPECS = (
    ("A_CHAR", "CHAR", "CHAR"),
    ("A_L2", "L2", "L2"),
    ("A_LOC", "LOC", "LOC"),
    ("B_CHAR__L2", "CHAR", "L2"),
    ("B_CHAR__LOC", "CHAR", "LOC"),
    ("B_L2__LOC", "L2", "LOC"),
    ("A_PRAC__PRAC", "PRAC", "PRAC"),
    ("B_PRAC__INFRA", "PRAC", "INFRA"),
    ("B_PRAC__GOV", "PRAC", "GOV"),
    ("A_INFRA__INFRA", "INFRA", "INFRA"),
    ("B_INFRA__GOV", "INFRA", "GOV"),
    ("A_GOV__GOV", "GOV", "GOV"),
)


@dataclass(frozen=True)
class MentionRecord:
    document_id: str
    sentence_id: str
    canonical_id: str
    canonical_name: str
    category: str
    text: str
    start: int
    end: int
    context: str | None
    ambiguity: str | None
    mention_id: str | None = None


@dataclass(frozen=True)
class NodeRecord:
    matrix_index: int
    category_index: int
    layer_index: int
    canonical_id: str
    canonical_name: str
    category: str
    layer: str
    mention_count: int
    sentence_count: int
    document_count: int
    ambiguity_low: int
    ambiguity_medium: int
    ambiguity_high: int
    ambiguity_other: int


@dataclass(frozen=True)
class SentenceRecord:
    matrix_row: int
    document_id: str
    sentence_id: str
    context: str
    mention_count: int
    unique_node_count: int


@dataclass(frozen=True)
class EdgeObservation:
    source_index: int
    target_index: int
    sentence_row: int
    document_id: str
    sentence_id: str
    source_mention_count: int
    target_mention_count: int
    source_texts: tuple[str, ...]
    target_texts: tuple[str, ...]
    source_ambiguities: tuple[str, ...]
    target_ambiguities: tuple[str, ...]


@dataclass(frozen=True)
class CooccurrenceResult:
    nodes: tuple[NodeRecord, ...]
    sentences: tuple[SentenceRecord, ...]
    incidence_entries: tuple[tuple[int, int, int], ...]
    edge_weights: dict[tuple[int, int], int]
    edge_documents: dict[tuple[int, int], frozenset[str]]
    observations: tuple[EdgeObservation, ...]


def _ordered_category_pair(category_a: str, category_b: str) -> tuple[str, str]:
    if CATEGORY_RANK[category_a] <= CATEGORY_RANK[category_b]:
        return category_a, category_b
    return category_b, category_a


def _distinct_strings(values: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}, key=str.casefold))


def _validate_mentions(mentions: Sequence[MentionRecord]) -> None:
    if not mentions:
        raise ValueError("No hay menciones para construir la coocurrencia")

    canonical_metadata: dict[str, tuple[str, str]] = {}
    for mention in mentions:
        if not mention.document_id:
            raise ValueError("Una mención no tiene document_id")
        if not mention.sentence_id:
            raise ValueError("Una mención no tiene sentence_id")
        if not mention.canonical_id:
            raise ValueError("Una mención no tiene canonical_id")
        if mention.category not in CATEGORY_RANK:
            raise ValueError(f"Categoría no permitida: {mention.category!r}")
        if not mention.canonical_name:
            raise ValueError("Una entidad canónica no tiene canonical_name")
        if mention.start < 0 or mention.end <= mention.start:
            raise ValueError(
                f"Offsets inválidos para la mención {mention.mention_id!r}"
            )

        metadata = (mention.canonical_name, mention.category)
        previous = canonical_metadata.setdefault(mention.canonical_id, metadata)
        if previous != metadata:
            raise ValueError(
                "El mismo canonical_id tiene nombres o categorías incompatibles: "
                f"{mention.canonical_id}"
            )


def build_sentence_cooccurrence(
    mentions: Sequence[MentionRecord],
) -> CooccurrenceResult:
    """Construye presencia oración–nodo y coocurrencias binarias por oración."""

    _validate_mentions(mentions)

    units: dict[tuple[str, str], list[MentionRecord]] = defaultdict(list)
    mentions_by_node: dict[str, list[MentionRecord]] = defaultdict(list)
    sentence_keys_by_node: dict[str, set[tuple[str, str]]] = defaultdict(set)
    document_ids_by_node: dict[str, set[str]] = defaultdict(set)
    canonical_metadata: dict[str, tuple[str, str]] = {}

    for mention in mentions:
        sentence_key = (mention.document_id, mention.sentence_id)
        units[sentence_key].append(mention)
        mentions_by_node[mention.canonical_id].append(mention)
        sentence_keys_by_node[mention.canonical_id].add(sentence_key)
        document_ids_by_node[mention.canonical_id].add(mention.document_id)
        canonical_metadata[mention.canonical_id] = (
            mention.canonical_name,
            mention.category,
        )

    ordered_node_ids = sorted(
        canonical_metadata,
        key=lambda canonical_id: (
            CATEGORY_RANK[canonical_metadata[canonical_id][1]],
            canonical_metadata[canonical_id][0].casefold(),
            canonical_id,
        ),
    )

    category_indexes: Counter[str] = Counter()
    layer_indexes: Counter[str] = Counter()
    nodes: list[NodeRecord] = []
    index_by_node: dict[str, int] = {}

    for matrix_index, canonical_id in enumerate(ordered_node_ids):
        canonical_name, category = canonical_metadata[canonical_id]
        layer = LAYER_BY_CATEGORY[category]
        node_mentions = mentions_by_node[canonical_id]
        ambiguity_counts = Counter(
            (
                mention.ambiguity
                if mention.ambiguity in {"low", "medium", "high"}
                else "other"
            )
            for mention in node_mentions
        )
        nodes.append(
            NodeRecord(
                matrix_index=matrix_index,
                category_index=category_indexes[category],
                layer_index=layer_indexes[layer],
                canonical_id=canonical_id,
                canonical_name=canonical_name,
                category=category,
                layer=layer,
                mention_count=len(node_mentions),
                sentence_count=len(sentence_keys_by_node[canonical_id]),
                document_count=len(document_ids_by_node[canonical_id]),
                ambiguity_low=ambiguity_counts["low"],
                ambiguity_medium=ambiguity_counts["medium"],
                ambiguity_high=ambiguity_counts["high"],
                ambiguity_other=ambiguity_counts["other"],
            )
        )
        index_by_node[canonical_id] = matrix_index
        category_indexes[category] += 1
        layer_indexes[layer] += 1

    sentences: list[SentenceRecord] = []
    incidence_entries: list[tuple[int, int, int]] = []
    edge_weights: Counter[tuple[int, int]] = Counter()
    edge_documents_mutable: dict[tuple[int, int], set[str]] = defaultdict(set)
    observations: list[EdgeObservation] = []

    for sentence_row, sentence_key in enumerate(sorted(units)):
        document_id, sentence_id = sentence_key
        sentence_mentions = units[sentence_key]
        contexts = {mention.context for mention in sentence_mentions if mention.context}
        if len(contexts) > 1:
            raise ValueError(
                "Una misma unidad document_id/sentence_id tiene contextos distintos: "
                f"{document_id}/{sentence_id}"
            )
        context = next(iter(contexts), "")

        mentions_by_index: dict[int, list[MentionRecord]] = defaultdict(list)
        for mention in sentence_mentions:
            mentions_by_index[index_by_node[mention.canonical_id]].append(mention)

        unique_indexes = sorted(mentions_by_index)
        incidence_entries.extend(
            (sentence_row, node_index, 1) for node_index in unique_indexes
        )
        sentences.append(
            SentenceRecord(
                matrix_row=sentence_row,
                document_id=document_id,
                sentence_id=sentence_id,
                context=context,
                mention_count=len(sentence_mentions),
                unique_node_count=len(unique_indexes),
            )
        )

        for source_index, target_index in combinations(unique_indexes, 2):
            edge_key = (source_index, target_index)
            edge_weights[edge_key] += 1
            edge_documents_mutable[edge_key].add(document_id)

            source_mentions = mentions_by_index[source_index]
            target_mentions = mentions_by_index[target_index]
            observations.append(
                EdgeObservation(
                    source_index=source_index,
                    target_index=target_index,
                    sentence_row=sentence_row,
                    document_id=document_id,
                    sentence_id=sentence_id,
                    source_mention_count=len(source_mentions),
                    target_mention_count=len(target_mentions),
                    source_texts=_distinct_strings(
                        mention.text for mention in source_mentions
                    ),
                    target_texts=_distinct_strings(
                        mention.text for mention in target_mentions
                    ),
                    source_ambiguities=_distinct_strings(
                        mention.ambiguity for mention in source_mentions
                    ),
                    target_ambiguities=_distinct_strings(
                        mention.ambiguity for mention in target_mentions
                    ),
                )
            )

    return CooccurrenceResult(
        nodes=tuple(nodes),
        sentences=tuple(sentences),
        incidence_entries=tuple(incidence_entries),
        edge_weights=dict(sorted(edge_weights.items())),
        edge_documents={
            edge: frozenset(document_ids)
            for edge, document_ids in edge_documents_mutable.items()
        },
        observations=tuple(observations),
    )


def _mention_signature(
    *,
    category: Any,
    text: Any,
    start: Any,
    end: Any,
    sentence_id: Any,
    context: Any,
    ambiguity: Any,
) -> tuple[Any, ...]:
    return (category, text, start, end, sentence_id, context, ambiguity)


def validate_json_against_db(
    json_entities: Sequence[dict[str, Any]],
    db_mentions: Sequence[MentionRecord],
) -> None:
    """Comprueba que JSON y PostgreSQL contienen las mismas menciones."""

    json_counter = Counter(
        _mention_signature(
            category=entity.get("category"),
            text=entity.get("text"),
            start=entity.get("start"),
            end=entity.get("end"),
            sentence_id=entity.get("sentence_id"),
            context=entity.get("context"),
            ambiguity=entity.get("ambiguity"),
        )
        for entity in json_entities
    )
    db_counter = Counter(
        _mention_signature(
            category=mention.category,
            text=mention.text,
            start=mention.start,
            end=mention.end,
            sentence_id=mention.sentence_id,
            context=mention.context,
            ambiguity=mention.ambiguity,
        )
        for mention in db_mentions
    )

    if json_counter == db_counter:
        return

    missing_in_db = json_counter - db_counter
    extra_in_db = db_counter - json_counter
    raise ValueError(
        "El JSON y PostgreSQL no representan las mismas menciones. "
        f"Faltantes en DB: {sum(missing_in_db.values())}; "
        f"adicionales en DB: {sum(extra_in_db.values())}"
    )


def load_ner_json(path: Path) -> tuple[str, list[dict[str, Any]]]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError("El archivo NER debe contener un objeto JSON")
    document_id = payload.get("document_id")
    entities = payload.get("entities")
    if not isinstance(document_id, str):
        raise ValueError("El archivo NER no tiene document_id válido")
    UUID(document_id)
    if not isinstance(entities, list) or not all(
        isinstance(entity, dict) for entity in entities
    ):
        raise ValueError("El archivo NER no tiene una lista entities válida")
    return document_id, entities


def load_db_mentions(document_id: str) -> list[MentionRecord]:
    """Consulta menciones canonicalizadas sin modificar PostgreSQL."""

    from sqlalchemy import select

    from src.models.canonical_entities import CanonicalEntity
    from src.models.database import SessionLocal
    from src.models.documents import Document  # noqa: F401 - configura el mapper
    from src.models.entities import Entity

    statement = (
        select(
            Entity.id.label("mention_id"),
            Entity.document_id,
            Entity.canonical_id,
            Entity.category.label("mention_category"),
            Entity.text,
            Entity.position_start,
            Entity.position_end,
            Entity.sentence_id,
            Entity.context,
            Entity.ambiguity,
            CanonicalEntity.canonical_name,
            CanonicalEntity.category.label("canonical_category"),
        )
        .join(CanonicalEntity, CanonicalEntity.id == Entity.canonical_id)
        .where(Entity.document_id == UUID(document_id))
        .order_by(Entity.position_start, Entity.position_end, Entity.id)
    )

    with SessionLocal() as db:
        rows = db.execute(statement).all()

    mentions: list[MentionRecord] = []
    for row in rows:
        if row.mention_category != row.canonical_category:
            raise ValueError(
                "Categoría inconsistente entre mención y canónico para "
                f"{row.mention_id}"
            )
        if row.canonical_id is None or row.sentence_id is None:
            raise ValueError(
                f"La mención {row.mention_id} no tiene canonical_id o sentence_id"
            )
        if row.position_start is None or row.position_end is None:
            raise ValueError(f"La mención {row.mention_id} no tiene offsets")
        mentions.append(
            MentionRecord(
                mention_id=str(row.mention_id),
                document_id=str(row.document_id),
                sentence_id=row.sentence_id,
                canonical_id=str(row.canonical_id),
                canonical_name=row.canonical_name,
                category=row.canonical_category,
                text=row.text,
                start=row.position_start,
                end=row.position_end,
                context=row.context,
                ambiguity=row.ambiguity,
            )
        )

    return mentions


def _write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_matrix_market(
    path: Path,
    row_count: int,
    column_count: int,
    entries: Sequence[tuple[int, int, int]],
    description: str,
) -> None:
    """Escribe una matriz dispersa; entradas del API usan índices base cero."""

    ordered_entries = sorted(entries, key=lambda entry: (entry[0], entry[1]))
    with path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("%%MatrixMarket matrix coordinate integer general\n")
        file.write(f"% {description}\n")
        file.write("% Los índices de este formato son base uno.\n")
        file.write(f"{row_count} {column_count} {len(ordered_entries)}\n")
        for row_index, column_index, value in ordered_entries:
            file.write(f"{row_index + 1} {column_index + 1} {value}\n")


def _node_csv_row(node: NodeRecord) -> dict[str, Any]:
    return {
        "matrix_index": node.matrix_index,
        "category_index": node.category_index,
        "layer_index": node.layer_index,
        "canonical_id": node.canonical_id,
        "canonical_name": node.canonical_name,
        "category": node.category,
        "layer": node.layer,
        "mention_count": node.mention_count,
        "sentence_count": node.sentence_count,
        "document_count": node.document_count,
        "ambiguity_low": node.ambiguity_low,
        "ambiguity_medium": node.ambiguity_medium,
        "ambiguity_high": node.ambiguity_high,
        "ambiguity_other": node.ambiguity_other,
    }


NODE_FIELDS = (
    "matrix_index",
    "category_index",
    "layer_index",
    "canonical_id",
    "canonical_name",
    "category",
    "layer",
    "mention_count",
    "sentence_count",
    "document_count",
    "ambiguity_low",
    "ambiguity_medium",
    "ambiguity_high",
    "ambiguity_other",
)


def _export_blocks(
    result: CooccurrenceResult,
    output_dir: Path,
) -> list[dict[str, Any]]:
    blocks_dir = output_dir / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)

    group_nodes: dict[str, list[NodeRecord]] = {}
    group_indexes: dict[str, dict[int, int]] = {}
    for group_name, categories in GROUP_CATEGORIES.items():
        nodes = [node for node in result.nodes if node.category in categories]
        group_nodes[group_name] = nodes
        group_indexes[group_name] = {
            node.matrix_index: local_index for local_index, node in enumerate(nodes)
        }
        _write_csv(
            blocks_dir / f"nodes_{group_name}.csv",
            ("block_index",) + NODE_FIELDS,
            (
                {"block_index": local_index, **_node_csv_row(node)}
                for local_index, node in enumerate(nodes)
            ),
        )

    manifest: list[dict[str, Any]] = []
    for matrix_name, row_group, column_group in BLOCK_SPECS:
        row_indexes = group_indexes[row_group]
        column_indexes = group_indexes[column_group]
        entries: list[tuple[int, int, int]] = []
        undirected_edge_count = 0
        total_weight = 0

        for (source_index, target_index), weight in result.edge_weights.items():
            if row_group == column_group:
                if source_index in row_indexes and target_index in row_indexes:
                    source_local = row_indexes[source_index]
                    target_local = row_indexes[target_index]
                    entries.extend(
                        (
                            (source_local, target_local, weight),
                            (target_local, source_local, weight),
                        )
                    )
                    undirected_edge_count += 1
                    total_weight += weight
                continue

            if source_index in row_indexes and target_index in column_indexes:
                entries.append(
                    (row_indexes[source_index], column_indexes[target_index], weight)
                )
            elif target_index in row_indexes and source_index in column_indexes:
                entries.append(
                    (row_indexes[target_index], column_indexes[source_index], weight)
                )
            else:
                continue
            undirected_edge_count += 1
            total_weight += weight

        filename = f"{matrix_name}.mtx"
        write_matrix_market(
            blocks_dir / filename,
            len(group_nodes[row_group]),
            len(group_nodes[column_group]),
            entries,
            f"Bloque de coocurrencia {row_group} x {column_group}",
        )
        manifest.append(
            {
                "matrix": matrix_name,
                "filename": filename,
                "row_group": row_group,
                "column_group": column_group,
                "rows": len(group_nodes[row_group]),
                "columns": len(group_nodes[column_group]),
                "nonzero_cells": len(entries),
                "undirected_edge_count": undirected_edge_count,
                "total_sentence_cooccurrences": total_weight,
            }
        )

    _write_csv(
        blocks_dir / "manifest.csv",
        (
            "matrix",
            "filename",
            "row_group",
            "column_group",
            "rows",
            "columns",
            "nonzero_cells",
            "undirected_edge_count",
            "total_sentence_cooccurrences",
        ),
        manifest,
    )
    return manifest


def _category_pair_rows(result: CooccurrenceResult) -> list[dict[str, Any]]:
    category_node_counts = Counter(node.category for node in result.nodes)
    weights_by_pair: dict[tuple[str, str], list[int]] = defaultdict(list)

    for (source_index, target_index), weight in result.edge_weights.items():
        source = result.nodes[source_index]
        target = result.nodes[target_index]
        category_pair = _ordered_category_pair(source.category, target.category)
        weights_by_pair[category_pair].append(weight)

    rows: list[dict[str, Any]] = []
    for first_index, source_category in enumerate(CATEGORY_ORDER):
        for target_category in CATEGORY_ORDER[first_index:]:
            pair = (source_category, target_category)
            weights = weights_by_pair[pair]
            source_nodes = category_node_counts[source_category]
            target_nodes = category_node_counts[target_category]
            if source_category == target_category:
                possible_pairs = source_nodes * (source_nodes - 1) // 2
            else:
                possible_pairs = source_nodes * target_nodes
            edge_count = len(weights)
            rows.append(
                {
                    "source_category": source_category,
                    "target_category": target_category,
                    "source_nodes": source_nodes,
                    "target_nodes": target_nodes,
                    "possible_pairs": possible_pairs,
                    "observed_edges": edge_count,
                    "density": (
                        round(edge_count / possible_pairs, 8) if possible_pairs else 0.0
                    ),
                    "total_sentence_cooccurrences": sum(weights),
                    "mean_weight_observed_edges": (
                        round(sum(weights) / edge_count, 6) if edge_count else 0.0
                    ),
                    "max_weight": max(weights, default=0),
                }
            )
    return rows


def export_result(
    result: CooccurrenceResult,
    output_dir: Path,
    *,
    document_id: str,
    ner_json_path: Path,
    json_mention_count: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        output_dir / "nodes.csv",
        NODE_FIELDS,
        (_node_csv_row(node) for node in result.nodes),
    )
    _write_csv(
        output_dir / "sentences.csv",
        (
            "matrix_row",
            "document_id",
            "sentence_id",
            "mention_count",
            "unique_node_count",
            "context",
        ),
        (
            {
                "matrix_row": sentence.matrix_row,
                "document_id": sentence.document_id,
                "sentence_id": sentence.sentence_id,
                "mention_count": sentence.mention_count,
                "unique_node_count": sentence.unique_node_count,
                "context": sentence.context,
            }
            for sentence in result.sentences
        ),
    )

    write_matrix_market(
        output_dir / "sentence_node_incidence.mtx",
        len(result.sentences),
        len(result.nodes),
        result.incidence_entries,
        "Matriz binaria oración x entidad canónica",
    )

    adjacency_entries: list[tuple[int, int, int]] = []
    for (source_index, target_index), weight in result.edge_weights.items():
        adjacency_entries.extend(
            (
                (source_index, target_index, weight),
                (target_index, source_index, weight),
            )
        )
    write_matrix_market(
        output_dir / "cooccurrence_adjacency.mtx",
        len(result.nodes),
        len(result.nodes),
        adjacency_entries,
        "Matriz simétrica de coocurrencia; diagonal igual a cero",
    )

    edge_rows: list[dict[str, Any]] = []
    for (source_index, target_index), weight in result.edge_weights.items():
        source = result.nodes[source_index]
        target = result.nodes[target_index]
        category_pair = _ordered_category_pair(source.category, target.category)
        edge_rows.append(
            {
                "source_index": source_index,
                "target_index": target_index,
                "source_canonical_id": source.canonical_id,
                "target_canonical_id": target.canonical_id,
                "source_name": source.canonical_name,
                "target_name": target.canonical_name,
                "source_category": source.category,
                "target_category": target.category,
                "source_layer": source.layer,
                "target_layer": target.layer,
                "category_pair": "--".join(category_pair),
                "layer_pair": "--".join(
                    sorted(
                        (source.layer, target.layer), key=("CHAR", "L2", "LOC").index
                    )
                ),
                "sentence_count": weight,
                "document_count": len(
                    result.edge_documents[(source_index, target_index)]
                ),
            }
        )

    _write_csv(
        output_dir / "edges.csv",
        (
            "source_index",
            "target_index",
            "source_canonical_id",
            "target_canonical_id",
            "source_name",
            "target_name",
            "source_category",
            "target_category",
            "source_layer",
            "target_layer",
            "category_pair",
            "layer_pair",
            "sentence_count",
            "document_count",
        ),
        edge_rows,
    )

    nodes_by_index = {node.matrix_index: node for node in result.nodes}
    _write_csv(
        output_dir / "edge_observations.csv",
        (
            "source_index",
            "target_index",
            "source_canonical_id",
            "target_canonical_id",
            "source_name",
            "target_name",
            "source_category",
            "target_category",
            "sentence_row",
            "document_id",
            "sentence_id",
            "source_mention_count",
            "target_mention_count",
            "source_texts",
            "target_texts",
            "source_ambiguities",
            "target_ambiguities",
        ),
        (
            {
                "source_index": observation.source_index,
                "target_index": observation.target_index,
                "source_canonical_id": nodes_by_index[
                    observation.source_index
                ].canonical_id,
                "target_canonical_id": nodes_by_index[
                    observation.target_index
                ].canonical_id,
                "source_name": nodes_by_index[observation.source_index].canonical_name,
                "target_name": nodes_by_index[observation.target_index].canonical_name,
                "source_category": nodes_by_index[observation.source_index].category,
                "target_category": nodes_by_index[observation.target_index].category,
                "sentence_row": observation.sentence_row,
                "document_id": observation.document_id,
                "sentence_id": observation.sentence_id,
                "source_mention_count": observation.source_mention_count,
                "target_mention_count": observation.target_mention_count,
                "source_texts": " | ".join(observation.source_texts),
                "target_texts": " | ".join(observation.target_texts),
                "source_ambiguities": " | ".join(observation.source_ambiguities),
                "target_ambiguities": " | ".join(observation.target_ambiguities),
            }
            for observation in result.observations
        ),
    )

    category_rows = _category_pair_rows(result)
    _write_csv(
        output_dir / "category_pair_summary.csv",
        (
            "source_category",
            "target_category",
            "source_nodes",
            "target_nodes",
            "possible_pairs",
            "observed_edges",
            "density",
            "total_sentence_cooccurrences",
            "mean_weight_observed_edges",
            "max_weight",
        ),
        category_rows,
    )

    block_manifest = _export_blocks(result, output_dir)
    category_counts = Counter(node.category for node in result.nodes)
    ambiguity_counts = Counter()
    for node in result.nodes:
        ambiguity_counts["low"] += node.ambiguity_low
        ambiguity_counts["medium"] += node.ambiguity_medium
        ambiguity_counts["high"] += node.ambiguity_high
        ambiguity_counts["other"] += node.ambiguity_other

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "document_id": document_id,
        "ner_json": str(ner_json_path),
        "definition": {
            "node": "canonical_id",
            "unit": "(document_id, sentence_id)",
            "edge": "dos canonical_id distintos presentes en la misma unidad",
            "weight": "numero de oraciones distintas donde coocurre el par",
            "deduplicate_node_within_sentence": True,
            "self_loops": False,
            "directed": False,
            "ambiguity_policy": "include_all",
            "normalization": "none",
        },
        "indexing": {
            "csv": "base_zero",
            "matrix_market": "base_one_per_format_specification",
        },
        "counts": {
            "json_mentions": json_mention_count,
            "database_mentions": sum(node.mention_count for node in result.nodes),
            "sentences": len(result.sentences),
            "canonical_nodes": len(result.nodes),
            "sentence_node_presences": len(result.incidence_entries),
            "undirected_edges": len(result.edge_weights),
            "edge_observations": len(result.observations),
            "total_sentence_cooccurrences": sum(result.edge_weights.values()),
            "max_edge_weight": max(result.edge_weights.values(), default=0),
        },
        "canonical_nodes_by_category": {
            category: category_counts[category] for category in CATEGORY_ORDER
        },
        "mentions_by_ambiguity": dict(ambiguity_counts),
        "blocks": block_manifest,
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construye matrices de coocurrencia por oración."
    )
    parser.add_argument(
        "--ner-json",
        required=True,
        type=Path,
        help="Archivo NER cuyo document_id delimita el corpus.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directorio de salida; por defecto data/output/cooccurrence/<document_id>.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    document_id, json_entities = load_ner_json(args.ner_json)
    db_mentions = load_db_mentions(document_id)
    validate_json_against_db(json_entities, db_mentions)
    result = build_sentence_cooccurrence(db_mentions)
    output_dir = args.output_dir or Path("data/output/cooccurrence") / document_id
    summary = export_result(
        result,
        output_dir,
        document_id=document_id,
        ner_json_path=args.ner_json,
        json_mention_count=len(json_entities),
    )
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    print(f"Resultados: {output_dir}")


if __name__ == "__main__":
    main()
