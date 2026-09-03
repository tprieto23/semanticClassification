"""Exportación mínima de grafos de coocurrencia a GraphML + CSV + metadata.

Este módulo reemplaza la generación masiva de artefactos (PNG, SVG, HTML,
matrices, evidencia CSV, vistas materializadas) por una salida compacta y
estable usada por el nuevo sistema de carpetas ``s3/graphs/``.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import networkx as nx

from src.analysis.cooccurrence import (
    NODE_FIELDS,
    CooccurrenceResult,
    category_pair_rows,
    ordered_category_pair,
)


def _write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _node_csv_row(node: Any) -> dict[str, Any]:
    return {
        "matrix_index": node.matrix_index,
        "category_index": getattr(node, "category_index", 0),
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


def _edge_csv_row(
    result: CooccurrenceResult,
    source_index: int,
    target_index: int,
    weight: int,
) -> dict[str, Any]:
    source = result.nodes[source_index]
    target = result.nodes[target_index]
    category_pair = ordered_category_pair(source.category, target.category)
    return {
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
        "document_count": len(result.edge_documents[(source_index, target_index)]),
    }


EDGE_FIELDS = (
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
)


def export_cooccurrence_graph(
    result: CooccurrenceResult,
    output_dir: Path,
    base_name: str,
    *,
    graph_metadata: dict[str, Any] | None = None,
    minimum_weight: int = 1,
    include_isolates: bool = True,
) -> dict[str, Any]:
    """Exporta un grafo de coocurrencia a GraphML y CSVs.

    Genera en ``output_dir``:
      - ``{base_name}.graphml``
      - ``{base_name}_nodes.csv``
      - ``{base_name}_edges.csv``

    Retorna un resumen con conteos y rutas relativas a ``output_dir``.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    graph = nx.Graph()
    metadata = graph_metadata or {
        "edge_definition": "same_sentence_cooccurrence",
        "directed": "false",
    }
    graph.graph.update({k: v for k, v in metadata.items() if v is not None})

    active_indexes = set(range(len(result.nodes)))
    if not include_isolates:
        active_indexes = {
            node_index
            for edge, weight in result.edge_weights.items()
            if weight >= minimum_weight
            for node_index in edge
        }

    for node in result.nodes:
        if node.matrix_index not in active_indexes:
            continue
        graph.add_node(
            node.canonical_id,
            label=node.canonical_name,
            **_node_csv_row(node),
        )

    included_edges: list[tuple[int, int, int]] = []
    for (source_index, target_index), weight in result.edge_weights.items():
        if weight < minimum_weight:
            continue
        if source_index not in active_indexes or target_index not in active_indexes:
            continue
        source = result.nodes[source_index]
        target = result.nodes[target_index]
        category_pair = ordered_category_pair(source.category, target.category)
        graph.add_edge(
            source.canonical_id,
            target.canonical_id,
            weight=weight,
            category_pair="--".join(category_pair),
            sentence_count=weight,
            document_count=len(result.edge_documents[(source_index, target_index)]),
        )
        included_edges.append((source_index, target_index, weight))

    graphml_path = output_dir / f"{base_name}.graphml"
    nodes_path = output_dir / f"{base_name}_nodes.csv"
    edges_path = output_dir / f"{base_name}_edges.csv"

    nx.write_graphml(graph, graphml_path)
    _write_csv(
        nodes_path,
        NODE_FIELDS,
        (_node_csv_row(result.nodes[index]) for index in sorted(active_indexes)),
    )
    _write_csv(
        edges_path,
        EDGE_FIELDS,
        (
            _edge_csv_row(result, source_index, target_index, weight)
            for source_index, target_index, weight in included_edges
        ),
    )

    components = list(nx.connected_components(graph))
    component_sizes = [len(component) for component in components]
    nodes_by_category = Counter(
        result.nodes[index].category for index in active_indexes
    )

    return {
        "graphml": graphml_path.name,
        "nodes_csv": nodes_path.name,
        "edges_csv": edges_path.name,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "components": len(components),
        "component_sizes": component_sizes,
        "nodes_by_category": dict(nodes_by_category),
        "edges_by_category_pair": dict(
            Counter(
                "--".join(
                    ordered_category_pair(
                        result.nodes[source].category,
                        result.nodes[target].category,
                    )
                )
                for source, target, _ in included_edges
            )
        ),
        "max_edge_weight": max(
            (weight for _, _, weight in included_edges),
            default=0,
        ),
    }


def write_metadata_json(
    path: Path,
    metadata: dict[str, Any],
) -> None:
    """Escribe el JSON de metadata en ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **metadata,
    }
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def build_metadata(
    *,
    scope_type: str,
    scope_id: str | int | None,
    language: str,
    base_name: str,
    filters: dict[str, Any],
    configuration: dict[str, Any],
    counts: dict[str, Any],
    outputs: dict[str, str],
    graph_hash: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Arma la metadata estándar para un artefacto de grafo."""
    return {
        "scope": f"{scope_type}:{scope_id or 'all'}:{language}",
        "scope_details": {
            "type": scope_type,
            "id": scope_id,
            "language": language,
        },
        "base_name": base_name,
        "filters": filters,
        "configuration": configuration,
        "counts": counts,
        "outputs": outputs,
        "hash": graph_hash,
        "metrics": metrics or {},
    }
