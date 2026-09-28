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
from itertools import combinations, combinations_with_replacement
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import UUID

CATEGORY_ORDER = ("CHAR", "LOC", "PRAC", "INFRA", "RUL")
CATEGORY_RANK = {category: index for index, category in enumerate(CATEGORY_ORDER)}
SEMANTIC_CORE_CATEGORIES = ("PRAC", "INFRA", "RUL")


def ordered_category_pair(category_a: str, category_b: str) -> tuple[str, str]:
    """Normaliza un par no dirigido siguiendo el orden canónico de categorías."""

    if category_a not in CATEGORY_RANK or category_b not in CATEGORY_RANK:
        raise ValueError(
            f"Par con categoría no permitida: {category_a!r}, {category_b!r}"
        )
    if CATEGORY_RANK[category_a] <= CATEGORY_RANK[category_b]:
        return category_a, category_b
    return category_b, category_a


def all_category_pairs(categories: Sequence[str]) -> tuple[tuple[str, str], ...]:
    ordered_categories = tuple(
        sorted(set(categories), key=lambda category: CATEGORY_RANK[category])
    )
    return tuple(
        ordered_category_pair(source, target)
        for source, target in combinations_with_replacement(ordered_categories, 2)
    )


def normalize_projection(
    node_categories: Sequence[str] | None = None,
    allowed_category_pairs: Sequence[tuple[str, str]] | None = None,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Valida y normaliza una proyección tipada no dirigida."""

    categories = tuple(
        sorted(
            set(node_categories or CATEGORY_ORDER),
            key=lambda category: CATEGORY_RANK.get(category, len(CATEGORY_ORDER)),
        )
    )
    if not categories:
        raise ValueError("La proyección debe incluir al menos una categoría")
    invalid_categories = [
        category for category in categories if category not in CATEGORY_RANK
    ]
    if invalid_categories:
        raise ValueError(
            "Categorías no permitidas en la proyección: "
            + ", ".join(invalid_categories)
        )

    category_set = set(categories)
    pairs = (
        all_category_pairs(categories)
        if allowed_category_pairs is None
        else tuple(
            sorted(
                {
                    ordered_category_pair(source, target)
                    for source, target in allowed_category_pairs
                },
                key=lambda pair: (CATEGORY_RANK[pair[0]], CATEGORY_RANK[pair[1]]),
            )
        )
    )
    if not pairs:
        raise ValueError("La proyección debe permitir al menos un category_pair")
    outside = [
        pair
        for pair in pairs
        if pair[0] not in category_set or pair[1] not in category_set
    ]
    if outside:
        formatted = ", ".join("--".join(pair) for pair in outside)
        raise ValueError(
            f"Los category_pair usan categorías fuera de node_categories: {formatted}"
        )
    return categories, pairs


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
    canonical_id: str
    canonical_name: str
    category: str
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
    projected_mention_count: int
    unique_entity_count: int
    unique_node_count: int


@dataclass(frozen=True)
class SentenceEntityRecord:
    sentence_row: int
    document_id: str
    sentence_id: str
    canonical_id: str
    canonical_name: str
    category: str
    is_projected: bool
    mention_count: int
    texts: tuple[str, ...]
    ambiguities: tuple[str, ...]


@dataclass(frozen=True)
class EdgeObservation:
    source_index: int
    target_index: int
    sentence_row: int
    document_id: str
    sentence_id: str
    context: str
    pair_context: str
    category_pair: tuple[str, str]
    source_mention_count: int
    target_mention_count: int
    source_texts: tuple[str, ...]
    target_texts: tuple[str, ...]
    source_ambiguities: tuple[str, ...]
    target_ambiguities: tuple[str, ...]


@dataclass(frozen=True)
class CooccurrenceResult:
    node_categories: tuple[str, ...]
    allowed_category_pairs: tuple[tuple[str, str], ...]
    source_mention_count: int
    projected_mention_count: int
    nodes: tuple[NodeRecord, ...]
    sentences: tuple[SentenceRecord, ...]
    sentence_entities: tuple[SentenceEntityRecord, ...]
    incidence_entries: tuple[tuple[int, int, int], ...]
    edge_weights: dict[tuple[int, int], int]
    edge_documents: dict[tuple[int, int], frozenset[str]]
    observations: tuple[EdgeObservation, ...]


def _ordered_category_pair(category_a: str, category_b: str) -> tuple[str, str]:
    return ordered_category_pair(category_a, category_b)


def _distinct_strings(values: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}, key=str.casefold))


def _merge_contexts(mentions: Sequence[MentionRecord]) -> str:
    """Une evidencia local distinta sin exigir un contexto global por oración."""

    contexts: list[str] = []
    seen: set[str] = set()
    for mention in sorted(mentions, key=lambda item: (item.start, item.end)):
        context = (mention.context or "").strip()
        if context and context not in seen:
            seen.add(context)
            contexts.append(context)
    return "\n…\n".join(contexts)


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
    *,
    node_categories: Sequence[str] | None = None,
    allowed_category_pairs: Sequence[tuple[str, str]] | None = None,
) -> CooccurrenceResult:
    """Construye una proyección tipada sin perder la evidencia de la oración.

    Los nodos, la incidencia y las aristas se limitan a ``node_categories`` y
    ``allowed_category_pairs``. Sin embargo, primero se agrupan todas las
    menciones; por eso ``sentence_entities`` conserva también CHAR/LOC u otras
    categorías contextuales que no formen parte de la proyección.
    """

    _validate_mentions(mentions)
    projected_categories, projected_pairs = normalize_projection(
        node_categories, allowed_category_pairs
    )
    projected_category_set = set(projected_categories)
    projected_pair_set = set(projected_pairs)

    units: dict[tuple[str, str], list[MentionRecord]] = defaultdict(list)
    mentions_by_node: dict[str, list[MentionRecord]] = defaultdict(list)
    sentence_keys_by_node: dict[str, set[tuple[str, str]]] = defaultdict(set)
    document_ids_by_node: dict[str, set[str]] = defaultdict(set)
    canonical_metadata: dict[str, tuple[str, str]] = {}

    for mention in mentions:
        sentence_key = (mention.document_id, mention.sentence_id)
        units[sentence_key].append(mention)
        if mention.category not in projected_category_set:
            continue
        mentions_by_node[mention.canonical_id].append(mention)
        sentence_keys_by_node[mention.canonical_id].add(sentence_key)
        document_ids_by_node[mention.canonical_id].add(mention.document_id)
        canonical_metadata[mention.canonical_id] = (
            mention.canonical_name,
            mention.category,
        )

    if not canonical_metadata:
        raise ValueError(
            "No hay menciones de las categorías seleccionadas para construir "
            "la proyección"
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
    nodes: list[NodeRecord] = []
    index_by_node: dict[str, int] = {}

    for matrix_index, canonical_id in enumerate(ordered_node_ids):
        canonical_name, category = canonical_metadata[canonical_id]
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
                canonical_id=canonical_id,
                canonical_name=canonical_name,
                category=category,
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

    sentences: list[SentenceRecord] = []
    sentence_entities: list[SentenceEntityRecord] = []
    incidence_entries: list[tuple[int, int, int]] = []
    edge_weights: Counter[tuple[int, int]] = Counter()
    edge_documents_mutable: dict[tuple[int, int], set[str]] = defaultdict(set)
    observations: list[EdgeObservation] = []

    for sentence_key in sorted(units):
        document_id, sentence_id = sentence_key
        sentence_mentions = units[sentence_key]
        projected_mentions = [
            mention
            for mention in sentence_mentions
            if mention.category in projected_category_set
        ]
        if not projected_mentions:
            continue

        sentence_row = len(sentences)
        sentence_context = _merge_contexts(sentence_mentions)

        mentions_by_index: dict[int, list[MentionRecord]] = defaultdict(list)
        for mention in projected_mentions:
            mentions_by_index[index_by_node[mention.canonical_id]].append(mention)

        mentions_by_canonical: dict[str, list[MentionRecord]] = defaultdict(list)
        for mention in sentence_mentions:
            mentions_by_canonical[mention.canonical_id].append(mention)

        for canonical_id, entity_mentions in sorted(
            mentions_by_canonical.items(),
            key=lambda item: (
                CATEGORY_RANK[item[1][0].category],
                item[1][0].canonical_name.casefold(),
                item[0],
            ),
        ):
            representative = entity_mentions[0]
            sentence_entities.append(
                SentenceEntityRecord(
                    sentence_row=sentence_row,
                    document_id=document_id,
                    sentence_id=sentence_id,
                    canonical_id=canonical_id,
                    canonical_name=representative.canonical_name,
                    category=representative.category,
                    is_projected=representative.category in projected_category_set,
                    mention_count=len(entity_mentions),
                    texts=_distinct_strings(
                        mention.text for mention in entity_mentions
                    ),
                    ambiguities=_distinct_strings(
                        mention.ambiguity for mention in entity_mentions
                    ),
                )
            )

        unique_indexes = sorted(mentions_by_index)
        incidence_entries.extend(
            (sentence_row, node_index, 1) for node_index in unique_indexes
        )
        sentences.append(
            SentenceRecord(
                matrix_row=sentence_row,
                document_id=document_id,
                sentence_id=sentence_id,
                context=sentence_context,
                mention_count=len(sentence_mentions),
                projected_mention_count=len(projected_mentions),
                unique_entity_count=len(mentions_by_canonical),
                unique_node_count=len(unique_indexes),
            )
        )

        for source_index, target_index in combinations(unique_indexes, 2):
            source_node = nodes[source_index]
            target_node = nodes[target_index]
            category_pair = ordered_category_pair(
                source_node.category, target_node.category
            )
            if category_pair not in projected_pair_set:
                continue
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
                    context=sentence_context,
                    pair_context=_merge_contexts(source_mentions + target_mentions),
                    category_pair=category_pair,
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
        node_categories=projected_categories,
        allowed_category_pairs=projected_pairs,
        source_mention_count=len(mentions),
        projected_mention_count=sum(
            1 for mention in mentions if mention.category in projected_category_set
        ),
        nodes=tuple(nodes),
        sentences=tuple(sentences),
        sentence_entities=tuple(sentence_entities),
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


def load_db_mentions(
    document_id: str | None = None,
    *,
    status: str | None = None,
    incubator_number: int | None = None,
    language: str | None = None,
    db: Any | None = None,
) -> list[MentionRecord]:
    """Consulta menciones canonicalizadas para un documento o un corpus."""

    from sqlalchemy import select

    from src.models.canonical_entities import CanonicalEntity
    from src.models.database import SessionLocal
    from src.models.documents import Document
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
        .join(Document, Document.id == Entity.document_id)
    )
    if document_id is not None:
        statement = statement.where(Entity.document_id == UUID(document_id))
    if status is not None:
        statement = statement.where(Document.status == status)
    if incubator_number is not None:
        statement = statement.where(Document.incubator_number == incubator_number)
    if language is not None:
        statement = statement.where(Document.language == language)
    statement = statement.order_by(
        Entity.document_id, Entity.position_start, Entity.position_end, Entity.id
    )

    if db is None:
        with SessionLocal() as owned_db:
            rows = owned_db.execute(statement).all()
    else:
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
        "canonical_id": node.canonical_id,
        "canonical_name": node.canonical_name,
        "category": node.category,
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
    "canonical_id",
    "canonical_name",
    "category",
    "mention_count",
    "sentence_count",
    "document_count",
    "ambiguity_low",
    "ambiguity_medium",
    "ambiguity_high",
    "ambiguity_other",
)


def category_pair_rows(
    result: CooccurrenceResult,
    minimum_weight: int = 1,
    *,
    include_isolates: bool = True,
) -> list[dict[str, Any]]:
    active_indexes = set(range(len(result.nodes)))
    if not include_isolates:
        active_indexes = {
            node_index
            for edge, weight in result.edge_weights.items()
            if weight >= minimum_weight
            for node_index in edge
        }
    category_node_counts = Counter(
        result.nodes[index].category for index in active_indexes
    )
    weights_by_pair: dict[tuple[str, str], list[int]] = defaultdict(list)

    for (source_index, target_index), weight in result.edge_weights.items():
        if weight < minimum_weight:
            continue
        source = result.nodes[source_index]
        target = result.nodes[target_index]
        category_pair = _ordered_category_pair(source.category, target.category)
        weights_by_pair[category_pair].append(weight)

    rows: list[dict[str, Any]] = []
    for source_category, target_category in result.allowed_category_pairs:
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
    scope: str | None = None,
    document_id: str | None = None,
    ner_json_path: Path | None = None,
    mention_count: int | None = None,
    json_mention_count: int | None = None,
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
            "projected_mention_count",
            "unique_entity_count",
            "unique_node_count",
            "context",
        ),
        (
            {
                "matrix_row": sentence.matrix_row,
                "document_id": sentence.document_id,
                "sentence_id": sentence.sentence_id,
                "mention_count": sentence.mention_count,
                "projected_mention_count": sentence.projected_mention_count,
                "unique_entity_count": sentence.unique_entity_count,
                "unique_node_count": sentence.unique_node_count,
                "context": sentence.context,
            }
            for sentence in result.sentences
        ),
    )

    _write_csv(
        output_dir / "sentence_entities.csv",
        (
            "sentence_row",
            "document_id",
            "sentence_id",
            "canonical_id",
            "canonical_name",
            "category",
            "is_projected",
            "mention_count",
            "texts",
            "ambiguities",
        ),
        (
            {
                "sentence_row": entity.sentence_row,
                "document_id": entity.document_id,
                "sentence_id": entity.sentence_id,
                "canonical_id": entity.canonical_id,
                "canonical_name": entity.canonical_name,
                "category": entity.category,
                "is_projected": str(entity.is_projected).lower(),
                "mention_count": entity.mention_count,
                "texts": " | ".join(entity.texts),
                "ambiguities": " | ".join(entity.ambiguities),
            }
            for entity in result.sentence_entities
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
                "category_pair": "--".join(category_pair),
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
            "category_pair",
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
            "category_pair",
            "sentence_row",
            "document_id",
            "sentence_id",
            "context",
            "pair_context",
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
                "category_pair": "--".join(observation.category_pair),
                "sentence_row": observation.sentence_row,
                "document_id": observation.document_id,
                "sentence_id": observation.sentence_id,
                "context": observation.context,
                "pair_context": observation.pair_context,
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

    category_rows = category_pair_rows(result)
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

    category_counts = Counter(node.category for node in result.nodes)
    ambiguity_counts = Counter()
    for node in result.nodes:
        ambiguity_counts["low"] += node.ambiguity_low
        ambiguity_counts["medium"] += node.ambiguity_medium
        ambiguity_counts["high"] += node.ambiguity_high
        ambiguity_counts["other"] += node.ambiguity_other

    resolved_scope = scope or f"document:{document_id}"
    resolved_source_mention_count = (
        mention_count
        if mention_count is not None
        else result.source_mention_count
    )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": resolved_scope,
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
            "projection": {
                "node_categories": list(result.node_categories),
                "category_pairs": [
                    "--".join(pair) for pair in result.allowed_category_pairs
                ],
                "context_categories_preserved_in_sentence_entities": True,
            },
        },
        "indexing": {
            "csv": "base_zero",
            "matrix_market": "base_one_per_format_specification",
        },
        "counts": {
            "mentions": result.projected_mention_count,
            "source_mentions": resolved_source_mention_count,
            "projected_mentions": result.projected_mention_count,
            "context_mentions_in_projected_sentences": sum(
                sentence.mention_count for sentence in result.sentences
            ),
            "sentences": len(result.sentences),
            "canonical_nodes": len(result.nodes),
            "sentence_node_presences": len(result.incidence_entries),
            "sentence_entity_presences": len(result.sentence_entities),
            "undirected_edges": len(result.edge_weights),
            "edge_observations": len(result.observations),
            "total_sentence_cooccurrences": sum(result.edge_weights.values()),
            "max_edge_weight": max(result.edge_weights.values(), default=0),
        },
        "canonical_nodes_by_category": {
            category: category_counts[category] for category in result.node_categories
        },
        "mentions_by_ambiguity": dict(ambiguity_counts),
    }
    if document_id is not None:
        summary["document_id"] = document_id
    if ner_json_path is not None:
        summary["ner_json"] = str(ner_json_path)
    if json_mention_count is not None:
        summary["counts"]["json_mentions"] = json_mention_count
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
