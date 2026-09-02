"""Construcción reproducible de backbones derivados de una proyección tipada.

La red de evidencia no se altera. Este módulo selecciona un núcleo analítico,
calcula pesos alternativos y exporta vistas GraphML/CSV auditables.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import networkx as nx

from src.analysis.cooccurrence import CooccurrenceResult, NodeRecord
from src.analysis.projections import ProjectionDefinition, ProjectionView

DOCUMENT_RECURRENT_CORE_METHOD = "document-recurrent-core-v1"
EDGE_WEIGHTINGS = (
    "sentence-count",
    "document-count",
    "fractional",
    "fractional-document",
)


@dataclass(frozen=True)
class DocumentRecurrentCoreConfig:
    method: str = DOCUMENT_RECURRENT_CORE_METHOD
    minimum_node_document_count: int = 2
    edge_weighting: str = "fractional-document"
    include_minor_components: bool = True

    def validate(self) -> None:
        if self.method != DOCUMENT_RECURRENT_CORE_METHOD:
            raise ValueError(f"Método de construcción no soportado: {self.method}")
        if self.minimum_node_document_count < 1:
            raise ValueError("minimum_node_document_count debe ser al menos 1")
        if self.edge_weighting not in EDGE_WEIGHTINGS:
            raise ValueError(
                "edge_weighting debe ser uno de: " + ", ".join(EDGE_WEIGHTINGS)
            )


@dataclass(frozen=True)
class BackboneBuildResult:
    graph: nx.Graph
    main_component_graph: nx.Graph
    eligible_node_count: int
    excluded_nodes: tuple[dict[str, Any], ...]
    excluded_edges: tuple[dict[str, Any], ...]


def _write_csv(
    path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _normalized_context(context: str) -> str:
    return " ".join(context.casefold().split())


def _node_attributes(node: NodeRecord) -> dict[str, Any]:
    return {
        "label": node.canonical_name,
        "canonical_id": node.canonical_id,
        "canonical_name": node.canonical_name,
        "category": node.category,
        "matrix_index": node.matrix_index,
        "mention_count": node.mention_count,
        "sentence_count": node.sentence_count,
        "document_count": node.document_count,
        "ambiguity_low": node.ambiguity_low,
        "ambiguity_medium": node.ambiguity_medium,
        "ambiguity_high": node.ambiguity_high,
        "ambiguity_other": node.ambiguity_other,
    }


def _analysis_weight(metrics: dict[str, Any], weighting: str) -> float:
    field = {
        "sentence-count": "sentence_count",
        "document-count": "document_count",
        "fractional": "fractional_weight",
        "fractional-document": "fractional_document_weight",
    }[weighting]
    return float(metrics[field])


def _ordered_components(graph: nx.Graph) -> list[set[str]]:
    return sorted(
        (set(component) for component in nx.connected_components(graph)),
        key=lambda component: (
            -len(component),
            tuple(
                sorted(
                    graph.nodes[node]["canonical_name"].casefold() for node in component
                )
            ),
        ),
    )


def _annotate_graph(graph: nx.Graph) -> nx.Graph:
    """Recalcula métricas para la topología exacta de una vista."""

    annotated = nx.Graph(graph)
    for component_index, component in enumerate(
        _ordered_components(annotated), start=1
    ):
        for node in component:
            annotated.nodes[node]["component"] = component_index
            annotated.nodes[node]["component_size"] = len(component)
    for node in annotated:
        annotated.nodes[node]["degree"] = annotated.degree(node)
        annotated.nodes[node]["strength"] = round(
            sum(
                float(attributes["analysis_weight"])
                for _, _, attributes in annotated.edges(node, data=True)
            ),
            12,
        )
        annotated.nodes[node]["raw_strength"] = sum(
            int(attributes["sentence_count"])
            for _, _, attributes in annotated.edges(node, data=True)
        )
        annotated.nodes[node]["document_strength"] = sum(
            int(attributes["document_count"])
            for _, _, attributes in annotated.edges(node, data=True)
        )
    return annotated


def build_document_recurrent_core(
    result: CooccurrenceResult,
    config: DocumentRecurrentCoreConfig,
) -> BackboneBuildResult:
    """Construye el subgrafo inducido por entidades recurrentes en documentos."""

    config.validate()
    nodes_by_index = {node.matrix_index: node for node in result.nodes}
    eligible_indexes = {
        node.matrix_index
        for node in result.nodes
        if node.document_count >= config.minimum_node_document_count
    }
    sentences_by_row = {sentence.matrix_row: sentence for sentence in result.sentences}
    observations_by_edge: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for observation in result.observations:
        observations_by_edge[
            (observation.source_index, observation.target_index)
        ].append(observation)

    graph = nx.Graph()
    excluded_edges: list[dict[str, Any]] = []
    for edge, sentence_count in result.edge_weights.items():
        source_index, target_index = edge
        source = nodes_by_index[source_index]
        target = nodes_by_index[target_index]
        if source_index not in eligible_indexes or target_index not in eligible_indexes:
            excluded_edges.append(
                {
                    "source_canonical_id": source.canonical_id,
                    "target_canonical_id": target.canonical_id,
                    "source_name": source.canonical_name,
                    "target_name": target.canonical_name,
                    "category_pair": f"{source.category}--{target.category}",
                    "sentence_count": sentence_count,
                    "document_count": len(result.edge_documents[edge]),
                    "exclusion_reason": "endpoint_below_node_document_threshold",
                }
            )
            continue

        observations = observations_by_edge[edge]
        fractional_weight = 0.0
        fractional_by_document: dict[str, float] = defaultdict(float)
        independent_supports: set[tuple[str, str]] = set()
        for observation in observations:
            sentence = sentences_by_row[observation.sentence_row]
            denominator = max(sentence.unique_node_count - 1, 1)
            contribution = 1.0 / denominator
            fractional_weight += contribution
            fractional_by_document[observation.document_id] += contribution
            independent_supports.add(
                (
                    observation.document_id,
                    _normalized_context(observation.context),
                )
            )
        document_count = len(result.edge_documents[edge])
        fractional_document_weight = sum(
            min(1.0, contribution) for contribution in fractional_by_document.values()
        )
        confidence_tier = (
            "transversal"
            if document_count >= 2
            else (
                "recurrent-local" if len(independent_supports) >= 2 else "exploratory"
            )
        )
        metrics = {
            "sentence_count": sentence_count,
            "document_count": document_count,
            "independent_support_count": len(independent_supports),
            "fractional_weight": round(fractional_weight, 12),
            "fractional_document_weight": round(fractional_document_weight, 12),
        }
        analysis_weight = round(_analysis_weight(metrics, config.edge_weighting), 12)
        graph.add_node(source.canonical_id, **_node_attributes(source))
        graph.add_node(target.canonical_id, **_node_attributes(target))
        graph.add_edge(
            source.canonical_id,
            target.canonical_id,
            weight=analysis_weight,
            analysis_weight=analysis_weight,
            analysis_weighting=config.edge_weighting,
            category_pair=f"{source.category}--{target.category}",
            confidence_tier=confidence_tier,
            **metrics,
        )

    graph = _annotate_graph(graph)
    included_ids = set(graph)
    excluded_nodes: list[dict[str, Any]] = []
    for node in result.nodes:
        if node.canonical_id in included_ids:
            continue
        reason = (
            "document_count_below_threshold"
            if node.matrix_index not in eligible_indexes
            else "no_edge_to_another_eligible_node"
        )
        excluded_nodes.append(
            {
                **_node_attributes(node),
                "exclusion_reason": reason,
            }
        )

    components = _ordered_components(graph)
    main_graph = (
        _annotate_graph(graph.subgraph(components[0]).copy())
        if components
        else nx.Graph()
    )
    return BackboneBuildResult(
        graph=graph,
        main_component_graph=main_graph,
        eligible_node_count=len(eligible_indexes),
        excluded_nodes=tuple(excluded_nodes),
        excluded_edges=tuple(excluded_edges),
    )


NODE_EXPORT_FIELDS = (
    "canonical_id",
    "canonical_name",
    "label",
    "category",
    "matrix_index",
    "mention_count",
    "sentence_count",
    "document_count",
    "degree",
    "strength",
    "raw_strength",
    "document_strength",
    "component",
    "component_size",
    "ambiguity_low",
    "ambiguity_medium",
    "ambiguity_high",
    "ambiguity_other",
)

EDGE_EXPORT_FIELDS = (
    "source_canonical_id",
    "target_canonical_id",
    "source_name",
    "target_name",
    "source_category",
    "target_category",
    "category_pair",
    "weight",
    "analysis_weight",
    "analysis_weighting",
    "sentence_count",
    "document_count",
    "independent_support_count",
    "fractional_weight",
    "fractional_document_weight",
    "confidence_tier",
)


def _node_rows(graph: nx.Graph) -> list[dict[str, Any]]:
    return [
        {field: graph.nodes[node].get(field, "") for field in NODE_EXPORT_FIELDS}
        for node in sorted(
            graph,
            key=lambda item: (
                int(graph.nodes[item].get("component", 0)),
                graph.nodes[item]["category"],
                graph.nodes[item]["canonical_name"].casefold(),
            ),
        )
    ]


def _edge_rows(graph: nx.Graph) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, target, attributes in sorted(
        graph.edges(data=True),
        key=lambda item: (
            -float(item[2]["analysis_weight"]),
            graph.nodes[item[0]]["canonical_name"].casefold(),
            graph.nodes[item[1]]["canonical_name"].casefold(),
        ),
    ):
        rows.append(
            {
                "source_canonical_id": source,
                "target_canonical_id": target,
                "source_name": graph.nodes[source]["canonical_name"],
                "target_name": graph.nodes[target]["canonical_name"],
                "source_category": graph.nodes[source]["category"],
                "target_category": graph.nodes[target]["category"],
                **{
                    field: attributes.get(field, "") for field in EDGE_EXPORT_FIELDS[6:]
                },
            }
        )
    return rows


def _view_graph(
    graph: nx.Graph,
    view: ProjectionView,
) -> nx.Graph:
    allowed_pairs = set(view.category_pair_labels)
    selected_edges = [
        (source, target)
        for source, target, attributes in graph.edges(data=True)
        if attributes["category_pair"] in allowed_pairs
    ]
    return _annotate_graph(graph.edge_subgraph(selected_edges).copy())


def _graph_summary(graph: nx.Graph) -> dict[str, Any]:
    components = _ordered_components(graph)
    return {
        "canonical_nodes": graph.number_of_nodes(),
        "undirected_edges": graph.number_of_edges(),
        "components": len(components),
        "component_sizes": [len(component) for component in components],
        "nodes_by_category": dict(
            sorted(
                Counter(
                    attributes["category"] for _, attributes in graph.nodes(data=True)
                ).items()
            )
        ),
        "edges_by_category_pair": dict(
            sorted(
                Counter(
                    attributes["category_pair"]
                    for _, _, attributes in graph.edges(data=True)
                ).items()
            )
        ),
        "edges_by_confidence_tier": dict(
            sorted(
                Counter(
                    attributes["confidence_tier"]
                    for _, _, attributes in graph.edges(data=True)
                ).items()
            )
        ),
        "max_analysis_weight": max(
            (
                float(attributes["analysis_weight"])
                for _, _, attributes in graph.edges(data=True)
            ),
            default=0.0,
        ),
    }


def _export_view(
    graph: nx.Graph,
    output_dir: Path,
    *,
    scope: str,
    projection: ProjectionDefinition,
    config: DocumentRecurrentCoreConfig,
    component_scope: str,
    view: ProjectionView,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = output_dir / "nodes.csv"
    edges_path = output_dir / "edges.csv"
    graphml_path = output_dir / "network.graphml"
    summary_path = output_dir / "summary.json"
    _write_csv(nodes_path, NODE_EXPORT_FIELDS, _node_rows(graph))
    _write_csv(edges_path, EDGE_EXPORT_FIELDS, _edge_rows(graph))

    graph_for_export = nx.Graph()
    graph_for_export.graph.update(
        {
            "scope": scope,
            "projection_id": projection.projection_id,
            "construction_method": config.method,
            "minimum_node_document_count": config.minimum_node_document_count,
            "edge_weighting": config.edge_weighting,
            "component_scope": component_scope,
            "semantic_view": view.view_id,
            "node_categories": ",".join(view.node_categories),
            "category_pairs": ",".join(view.category_pair_labels),
            "edge_definition": "same_sentence_cooccurrence",
        }
    )
    graph_for_export.add_nodes_from(graph.nodes(data=True))
    for source, target, attributes in graph.edges(data=True):
        graph_for_export.add_edge(
            source,
            target,
            edge_key="::".join(sorted((source, target))),
            **attributes,
        )
    nx.write_graphml(graph_for_export, graphml_path)

    summary = {
        "scope": scope,
        "projection_id": projection.projection_id,
        "construction": asdict(config),
        "component_scope": component_scope,
        "view": {
            "id": view.view_id,
            "label": view.label,
            "node_categories": list(view.node_categories),
            "category_pairs": list(view.category_pair_labels),
        },
        "counts": _graph_summary(graph),
        "outputs": {
            "graphml": graphml_path.name,
            "nodes_csv": nodes_path.name,
            "edges_csv": edges_path.name,
        },
    }
    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return summary


def export_document_recurrent_core(
    result: CooccurrenceResult,
    output_dir: Path,
    *,
    scope: str,
    projection: ProjectionDefinition,
    config: DocumentRecurrentCoreConfig,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Exporta el backbone, auditoría de exclusiones y todas sus vistas."""

    build = build_document_recurrent_core(result, config)
    backbone_dir = output_dir / "backbone"
    backbone_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(backbone_dir / "nodes.csv", NODE_EXPORT_FIELDS, _node_rows(build.graph))
    _write_csv(backbone_dir / "edges.csv", EDGE_EXPORT_FIELDS, _edge_rows(build.graph))

    excluded_node_fields = (*NODE_EXPORT_FIELDS[:8], "exclusion_reason")
    _write_csv(
        backbone_dir / "excluded_nodes.csv",
        excluded_node_fields,
        (
            {field: row.get(field, "") for field in excluded_node_fields}
            for row in build.excluded_nodes
        ),
    )
    excluded_edge_fields = (
        "source_canonical_id",
        "target_canonical_id",
        "source_name",
        "target_name",
        "category_pair",
        "sentence_count",
        "document_count",
        "exclusion_reason",
    )
    _write_csv(
        backbone_dir / "excluded_edges.csv",
        excluded_edge_fields,
        build.excluded_edges,
    )

    component_graphs = {
        "all-components": build.graph,
        "main-component": build.main_component_graph,
    }
    component_views: dict[str, dict[str, Any]] = {}
    for component_scope, component_graph in component_graphs.items():
        semantic_views: dict[str, Any] = {}
        for view in projection.views:
            graph = _view_graph(component_graph, view)
            relative = Path("views") / component_scope / view.view_id
            summary = _export_view(
                graph,
                output_dir / relative,
                scope=scope,
                projection=projection,
                config=config,
                component_scope=component_scope,
                view=view,
            )
            semantic_views[view.view_id] = {
                **summary["view"],
                "counts": summary["counts"],
                "outputs": {
                    name: (relative / filename).as_posix()
                    for name, filename in summary["outputs"].items()
                },
            }
        component_views[component_scope] = semantic_views

    edge_incident_indexes = {
        node_index for edge in result.edge_weights for node_index in edge
    }
    base_counts = {
        "canonical_nodes": len(result.nodes),
        "edge_incident_nodes": len(edge_incident_indexes),
        "isolated_nodes": len(result.nodes) - len(edge_incident_indexes),
        "undirected_edges": len(result.edge_weights),
        "sentences": len(result.sentences),
        "edge_observations": len(result.observations),
    }
    all_counts = _graph_summary(build.graph)
    main_counts = _graph_summary(build.main_component_graph)
    primary_scope = (
        "all-components" if config.include_minor_components else "main-component"
    )
    primary = component_views[primary_scope]["all"]
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "filters": filters or {},
        "projection_id": projection.projection_id,
        "construction": asdict(config),
        "definitions": {
            "eligible_node": (
                "node.document_count >= minimum_node_document_count within scope"
            ),
            "included_edge": "both endpoints are eligible",
            "fractional_weight": "sum over supporting sentences of 1/(N_s-1)",
            "fractional_document_weight": (
                "sum over documents of min(1, sum sentence contributions)"
            ),
            "independent_support_count": (
                "distinct (document_id, whitespace-normalized casefold context)"
            ),
            "weight": "selected analysis_weight for Gephi algorithms",
        },
        "base_network": base_counts,
        "eligibility": {
            "eligible_nodes_before_edge_induction": build.eligible_node_count,
            "excluded_nodes": len(build.excluded_nodes),
            "excluded_edges": len(build.excluded_edges),
        },
        "analytical_network": all_counts,
        "main_component": main_counts,
        "primary_component_scope": primary_scope,
    }
    manifest_path = output_dir / "construction_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return {
        **manifest,
        "primary_view": primary,
        "component_views": component_views,
        "outputs": {
            "construction_manifest_json": "construction_manifest.json",
            "backbone_nodes_csv": "backbone/nodes.csv",
            "backbone_edges_csv": "backbone/edges.csv",
            "excluded_nodes_csv": "backbone/excluded_nodes.csv",
            "excluded_edges_csv": "backbone/excluded_edges.csv",
            **primary["outputs"],
        },
    }
