"""Visualización del núcleo recurrente de una red de coocurrencia.

Consume los artefactos producidos por :mod:`src.analysis.cooccurrence`. La red
es no dirigida: una arista indica que dos entidades canónicas aparecen en la
misma oración, y su peso es el número de oraciones distintas donde coocurren.

El módulo no consulta ni modifica PostgreSQL. Produce figuras estáticas, un
HTML interactivo autosuficiente, tablas filtradas y un archivo GraphML.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import textwrap
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D

CATEGORY_ORDER = ("CHAR", "LOC", "PRAC", "INFRA", "GOV")
CATEGORY_STYLE = {
    "CHAR": {"color": "#E69F00", "shape": "o", "label": "CHAR"},
    "PRAC": {"color": "#009E73", "shape": "s", "label": "PRAC"},
    "INFRA": {"color": "#0072B2", "shape": "D", "label": "INFRA"},
    "GOV": {"color": "#CC79A7", "shape": "P", "label": "GOV"},
    "LOC": {"color": "#56B4E9", "shape": "h", "label": "LOC"},
}


@dataclass(frozen=True)
class NetworkData:
    graph: nx.Graph
    scope: str
    node_categories: tuple[str, ...]
    category_pairs: tuple[str, ...]
    minimum_weight: int
    includes_isolates: bool


@dataclass(frozen=True)
class NetworkEvidence:
    sentences: dict[str, dict[str, Any]]
    edge_references: dict[tuple[str, str], list[dict[str, Any]]]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo requerido: {path}")
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _read_summary(analysis_dir: Path) -> dict[str, Any]:
    path = analysis_dir / "summary.json"
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo requerido: {path}")
    with path.open(encoding="utf-8") as file:
        summary = json.load(file)
    if not isinstance(summary, dict):
        raise ValueError("summary.json no contiene un objeto válido")
    if not isinstance(summary.get("scope") or summary.get("document_id"), str):
        raise ValueError("summary.json no contiene un scope válido")
    return summary


def _int_field(row: dict[str, str], field: str, source: Path) -> int:
    try:
        return int(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Campo entero inválido {field!r} en {source}") from exc


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


def load_core_network(
    analysis_dir: Path,
    minimum_weight: int = 3,
    *,
    include_isolates: bool = False,
    node_categories: Sequence[str] | None = None,
    allowed_category_pairs: Sequence[str] | None = None,
) -> NetworkData:
    """Carga aristas que alcanzan el umbral y, opcionalmente, nodos aislados."""

    if minimum_weight < 1:
        raise ValueError("minimum_weight debe ser mayor o igual a 1")

    summary = _read_summary(analysis_dir)
    projection = summary.get("definition", {}).get("projection", {})
    selected_categories = tuple(
        node_categories or projection.get("node_categories") or CATEGORY_ORDER
    )
    selected_category_set = set(selected_categories)
    selected_pairs = tuple(
        allowed_category_pairs
        or projection.get("category_pairs")
        or (
            f"{source}--{target}"
            for source_index, source in enumerate(CATEGORY_ORDER)
            for target in CATEGORY_ORDER[source_index:]
        )
    )
    selected_pair_set = set(selected_pairs)
    nodes_path = analysis_dir / "nodes.csv"
    edges_path = analysis_dir / "edges.csv"
    node_rows = _read_csv(nodes_path)
    edge_rows = _read_csv(edges_path)

    metadata_by_id: dict[str, dict[str, Any]] = {}
    for row in node_rows:
        canonical_id = row.get("canonical_id", "")
        category = row.get("category", "")
        if not canonical_id or canonical_id in metadata_by_id:
            raise ValueError(f"canonical_id ausente o duplicado en {nodes_path}")
        if category not in CATEGORY_STYLE:
            raise ValueError(f"Categoría no permitida en {nodes_path}: {category!r}")
        if category not in selected_category_set:
            continue
        metadata_by_id[canonical_id] = {
            "canonical_id": canonical_id,
            "canonical_name": row.get("canonical_name", ""),
            "category": category,
            "matrix_index": _int_field(row, "matrix_index", nodes_path),
            "mention_count": _int_field(row, "mention_count", nodes_path),
            "sentence_count": _int_field(row, "sentence_count", nodes_path),
            "document_count": _int_field(row, "document_count", nodes_path),
            "ambiguity_low": _int_field(row, "ambiguity_low", nodes_path),
            "ambiguity_medium": _int_field(row, "ambiguity_medium", nodes_path),
            "ambiguity_high": _int_field(row, "ambiguity_high", nodes_path),
            "ambiguity_other": _int_field(row, "ambiguity_other", nodes_path),
        }

    graph = nx.Graph()
    for row in edge_rows:
        weight = _int_field(row, "sentence_count", edges_path)
        if weight < minimum_weight:
            continue
        if row.get("category_pair", "") not in selected_pair_set:
            continue
        source = row.get("source_canonical_id", "")
        target = row.get("target_canonical_id", "")
        if source == target:
            raise ValueError(f"Self-loop inesperado en {edges_path}: {source}")
        if source not in metadata_by_id or target not in metadata_by_id:
            raise ValueError(f"Arista con nodo desconocido en {edges_path}")
        if graph.has_edge(source, target):
            raise ValueError(f"Arista duplicada en {edges_path}: {source}/{target}")
        graph.add_node(source, **metadata_by_id[source])
        graph.add_node(target, **metadata_by_id[target])
        graph.add_edge(
            source,
            target,
            weight=weight,
            document_count=_int_field(row, "document_count", edges_path),
            category_pair=row.get("category_pair", ""),
        )

    if include_isolates:
        for canonical_id, metadata in metadata_by_id.items():
            graph.add_node(canonical_id, **metadata)

    for component_index, component in enumerate(_ordered_components(graph), start=1):
        for node in component:
            graph.nodes[node]["component"] = component_index
            graph.nodes[node]["component_size"] = len(component)

    for node in graph:
        graph.nodes[node]["degree"] = graph.degree(node)
        graph.nodes[node]["strength"] = sum(
            data["weight"] for _, _, data in graph.edges(node, data=True)
        )

    return NetworkData(
        graph=graph,
        scope=summary.get("scope") or f'document:{summary["document_id"]}',
        node_categories=selected_categories,
        category_pairs=selected_pairs,
        minimum_weight=minimum_weight,
        includes_isolates=include_isolates,
    )


def _normalize_component_positions(
    positions: dict[str, Any],
    width: float,
    height: float,
    center_x: float,
) -> dict[str, tuple[float, float]]:
    if len(positions) == 1:
        node = next(iter(positions))
        return {node: (center_x, 0.0)}
    xs = [float(position[0]) for position in positions.values()]
    ys = [float(position[1]) for position in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    x_span = max(max_x - min_x, 1.0)
    y_span = max(max_y - min_y, 1.0)
    return {
        node: (
            center_x + ((float(position[0]) - min_x) / x_span - 0.5) * width,
            ((float(position[1]) - min_y) / y_span - 0.5) * height,
        )
        for node, position in positions.items()
    }


def build_free_layout(
    graph: nx.Graph, seed: int = 42
) -> dict[str, tuple[float, float]]:
    """Calcula un diseño plano reproducible y escalable por componentes."""

    positions: dict[str, tuple[float, float]] = {}
    component_specs: list[tuple[set[str], float, float]] = []
    isolates: list[str] = []
    for component_index, component in enumerate(_ordered_components(graph), start=1):
        size = len(component)
        if size == 1:
            isolates.extend(component)
            continue
        width = max(2.8, math.sqrt(size) * 2.2)
        height = max(2.5, math.sqrt(size) * 1.8)
        if component_index == 1:
            # El componente principal concentra la mayor parte de las etiquetas y
            # necesita más superficie que los componentes pequeños para ser legible.
            width *= 1.75
            height *= 1.35
        component_specs.append((component, width, height))

    total_width = sum(width for _, width, _ in component_specs) + 1.5 * (
        len(component_specs) - 1
    )
    cursor = -total_width / 2
    for component_index, (component, width, height) in enumerate(
        component_specs, start=1
    ):
        subgraph = graph.subgraph(component)
        if len(component) > 500:
            # El spring layout deja de ser práctico para corpus con miles de nodos.
            # La espiral áurea conserva centralidad visual y tiene costo lineal.
            ordered_nodes = sorted(
                component,
                key=lambda node: (
                    -graph.nodes[node].get("strength", 0),
                    -graph.degree(node),
                    graph.nodes[node]["canonical_name"].casefold(),
                ),
            )
            golden_angle = math.pi * (3.0 - math.sqrt(5.0))
            local_positions = {
                node: (
                    math.sqrt(index) * math.cos(index * golden_angle),
                    math.sqrt(index) * math.sin(index * golden_angle),
                )
                for index, node in enumerate(ordered_nodes)
            }
        else:
            local_positions = nx.spring_layout(
                subgraph,
                seed=seed + component_index,
                weight="weight",
                iterations=250,
                k=1.2 / math.sqrt(max(len(component), 2)),
            )
        center_x = cursor + width / 2
        positions.update(
            _normalize_component_positions(local_positions, width, height, center_x)
        )
        cursor += width + 1.5

    if isolates:
        columns = max(1, math.ceil(math.sqrt(len(isolates))))
        spacing = 1.15
        center_offset = (columns - 1) * spacing / 2
        bottom = min((position[1] for position in positions.values()), default=2.0) - 4.0
        for index, node in enumerate(
            sorted(
                isolates,
                key=lambda item: (
                    CATEGORY_ORDER.index(graph.nodes[item]["category"]),
                    graph.nodes[item]["canonical_name"].casefold(),
                ),
            )
        ):
            row, column = divmod(index, columns)
            positions[node] = (column * spacing - center_offset, bottom - row * spacing)
    return positions


def _node_size(strength: int, maximum_strength: int) -> float:
    if maximum_strength <= 0:
        return 650.0
    return 520.0 + 1_180.0 * math.sqrt(strength / maximum_strength)


def _edge_width(weight: int, minimum_weight: int) -> float:
    return 1.0 + 0.85 * math.sqrt(max(weight - minimum_weight + 1, 1))


def _category_counts(graph: nx.Graph) -> Counter[str]:
    return Counter(graph.nodes[node]["category"] for node in graph)


def _draw_graph(
    graph: nx.Graph,
    positions: dict[str, tuple[float, float]],
    output_prefix: Path,
    *,
    title: str,
    subtitle: str,
    minimum_weight: int,
    category_order: Sequence[str] = CATEGORY_ORDER,
    label_limit: int | None = None,
    show_edge_labels: bool = True,
) -> None:
    figure, ax = plt.subplots(figsize=(18, 12), facecolor="#F8FAFC")
    ax.set_facecolor("#FFFFFF")

    if graph.number_of_nodes() == 0:
        ax.text(
            0.5,
            0.5,
            "La vista no contiene nodos con los filtros seleccionados.",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=14,
            color="#475569",
        )
        ax.set_title(title, fontsize=18, fontweight="bold", color="#0F172A", pad=24)
        ax.set_axis_off()
        output_prefix.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(
            output_prefix.with_suffix(".png"),
            dpi=220,
            bbox_inches="tight",
            facecolor=figure.get_facecolor(),
        )
        figure.savefig(
            output_prefix.with_suffix(".svg"),
            bbox_inches="tight",
            facecolor=figure.get_facecolor(),
        )
        plt.close(figure)
        return

    edge_list = list(graph.edges(data=True))
    nx.draw_networkx_edges(
        graph,
        positions,
        edgelist=[(source, target) for source, target, _ in edge_list],
        width=[_edge_width(data["weight"], minimum_weight) for _, _, data in edge_list],
        edge_color="#64748B",
        alpha=0.48,
        ax=ax,
    )

    maximum_strength = max(graph.nodes[node]["strength"] for node in graph)
    counts = _category_counts(graph)
    for category in category_order:
        category_nodes = [
            node for node in graph if graph.nodes[node]["category"] == category
        ]
        if not category_nodes:
            continue
        style = CATEGORY_STYLE[category]
        nx.draw_networkx_nodes(
            graph,
            positions,
            nodelist=category_nodes,
            node_color=style["color"],
            node_shape=style["shape"],
            node_size=[
                _node_size(graph.nodes[node]["strength"], maximum_strength)
                * 0.78
                for node in category_nodes
            ],
            edgecolors="#1E293B",
            linewidths=1.0,
            alpha=0.96,
            ax=ax,
        )

    points_by_component: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for node, position in positions.items():
        points_by_component[graph.nodes[node]["component"]].append(position)
    component_centers = {
        component: (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
        for component, points in points_by_component.items()
    }

    labelled_nodes = set(graph)
    if label_limit is not None:
        labelled_nodes = set(
            sorted(
                graph,
                key=lambda item: (
                    -graph.nodes[item]["strength"],
                    -graph.nodes[item]["degree"],
                    graph.nodes[item]["canonical_name"].casefold(),
                ),
            )[:label_limit]
        )

    for node, (x, y) in positions.items():
        if node not in labelled_nodes:
            continue
        offset_x = 0.0
        offset_y = 15.0
        horizontal_alignment = "center"
        vertical_alignment = "bottom"
        center_x, center_y = component_centers[graph.nodes[node]["component"]]
        delta_x, delta_y = x - center_x, y - center_y
        if abs(delta_x) > abs(delta_y) * 0.45:
            offset_x = 13.0 if delta_x >= 0 else -13.0
            offset_y = 2.0
            horizontal_alignment = "left" if delta_x >= 0 else "right"
            vertical_alignment = "center"
        else:
            offset_y = 16.0 if delta_y >= 0 else -17.0
            vertical_alignment = "bottom" if delta_y >= 0 else "top"
        label = textwrap.fill(graph.nodes[node]["canonical_name"], width=20)
        ax.annotate(
            label,
            (x, y),
            xytext=(offset_x, offset_y),
            textcoords="offset points",
            ha=horizontal_alignment,
            va=vertical_alignment,
            fontsize=7.6,
            color="#0F172A",
            bbox={
                "boxstyle": "round,pad=0.18",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.82,
            },
            zorder=5,
        )

    edge_labels = (
        {
            (source, target): data["weight"]
            for source, target, data in edge_list
            if data["weight"] > minimum_weight
        }
        if show_edge_labels
        else {}
    )
    nx.draw_networkx_edge_labels(
        graph,
        positions,
        edge_labels=edge_labels,
        font_size=7.5,
        font_color="#334155",
        bbox={
            "boxstyle": "round,pad=0.12",
            "facecolor": "white",
            "edgecolor": "#CBD5E1",
            "alpha": 0.9,
        },
        ax=ax,
    )

    legend_handles: list[Line2D] = []
    for category in category_order:
        style = CATEGORY_STYLE[category]
        legend_handles.append(
            Line2D(
                [0],
                [0],
                marker=style["shape"],
                color="none",
                markerfacecolor=style["color"],
                markeredgecolor="#1E293B",
                markersize=9,
                label=f"{category} ({counts[category]} nodos)",
            )
        )
    ax.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.10),
        ncol=max(1, len(category_order)),
        frameon=False,
        fontsize=8.5,
    )

    ax.set_title(title, fontsize=18, fontweight="bold", color="#0F172A", pad=24)
    ax.text(
        0.5,
        1.015,
        subtitle,
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#475569",
    )
    ax.text(
        0.5,
        -0.045,
        "Arista = coocurrencia en una misma oración · "
        "Grosor = número de oraciones · Sin dirección ni causalidad",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8.5,
        color="#64748B",
    )

    ax.margins(x=0.08, y=0.20)
    ax.set_axis_off()
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output_prefix.with_suffix(".png"),
        dpi=220,
        bbox_inches="tight",
        facecolor=figure.get_facecolor(),
    )
    figure.savefig(
        output_prefix.with_suffix(".svg"),
        bbox_inches="tight",
        facecolor=figure.get_facecolor(),
    )
    plt.close(figure)


def _normalize_for_svg(
    positions: dict[str, tuple[float, float]],
    *,
    width: int = 1_200,
    height: int = 780,
    padding_x: int = 90,
    padding_y: int = 75,
) -> dict[str, dict[str, float]]:
    if not positions:
        return {}
    xs = [position[0] for position in positions.values()]
    ys = [position[1] for position in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    x_span = max(max_x - min_x, 1.0)
    y_span = max(max_y - min_y, 1.0)
    return {
        node: {
            "x": padding_x + (position[0] - min_x) / x_span * (width - 2 * padding_x),
            "y": padding_y + (max_y - position[1]) / y_span * (height - 2 * padding_y),
        }
        for node, position in positions.items()
    }


def _edge_key(source: str, target: str) -> tuple[str, str]:
    return tuple(sorted((source, target)))  # type: ignore[return-value]


def _sentence_key(document_id: str, sentence_id: str) -> str:
    return f"{document_id}::{sentence_id}"


def load_edge_evidence(analysis_dir: Path, graph: nx.Graph) -> NetworkEvidence:
    sentences: dict[str, dict[str, Any]] = {}
    for row in _read_csv(analysis_dir / "sentences.csv"):
        key = _sentence_key(row["document_id"], row["sentence_id"])
        sentences[key] = {
            "documentId": row["document_id"],
            "sentenceId": row["sentence_id"],
            "context": row.get("context", ""),
            "projectedEntities": [],
            "contextEntities": [],
        }

    sentence_entities_path = analysis_dir / "sentence_entities.csv"
    if sentence_entities_path.exists():
        for row in _read_csv(sentence_entities_path):
            key = _sentence_key(row["document_id"], row["sentence_id"])
            sentence = sentences.get(key)
            if sentence is None:
                continue
            entity = {
                "canonicalId": row.get("canonical_id", ""),
                "canonicalName": row.get("canonical_name", ""),
                "category": row.get("category", ""),
                "mentionCount": int(row.get("mention_count") or 0),
                "texts": row.get("texts", ""),
            }
            sentence["contextEntities"].append(entity)
            if row.get("is_projected", "").casefold() == "true":
                sentence["projectedEntities"].append(entity)

    evidence: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _read_csv(analysis_dir / "edge_observations.csv"):
        source = row.get("source_canonical_id", "")
        target = row.get("target_canonical_id", "")
        if not graph.has_edge(source, target):
            continue
        sentence_key = _sentence_key(row["document_id"], row["sentence_id"])
        evidence[_edge_key(source, target)].append(
            {
                "sentenceKey": sentence_key,
                "pairContext": row.get("pair_context") or row.get("context", ""),
                "sourceTexts": row.get("source_texts", ""),
                "targetTexts": row.get("target_texts", ""),
                "sourceAmbiguities": row.get("source_ambiguities", ""),
                "targetAmbiguities": row.get("target_ambiguities", ""),
            }
        )
    referenced_sentence_keys = {
        item["sentenceKey"]
        for references in evidence.values()
        for item in references
    }
    return NetworkEvidence(
        sentences={
            key: sentence
            for key, sentence in sentences.items()
            if key in referenced_sentence_keys
        },
        edge_references=dict(evidence),
    )


def _interactive_payload(
    data: NetworkData,
    positions: dict[str, dict[str, float]],
    evidence: NetworkEvidence,
) -> dict[str, Any]:
    graph = data.graph
    maximum_strength = max((graph.nodes[node]["strength"] for node in graph), default=0)
    size_denominator = max(maximum_strength, 1)
    nodes = []
    for node in sorted(
        graph,
        key=lambda item: (
            CATEGORY_ORDER.index(graph.nodes[item]["category"]),
            graph.nodes[item]["canonical_name"].casefold(),
        ),
    ):
        attributes = graph.nodes[node]
        nodes.append(
            {
                "id": node,
                "name": attributes["canonical_name"],
                "category": attributes["category"],
                "mentionCount": attributes["mention_count"],
                "sentenceCount": attributes["sentence_count"],
                "degree": attributes["degree"],
                "strength": attributes["strength"],
                "component": attributes["component"],
                "componentSize": attributes["component_size"],
                "ambiguityLow": attributes["ambiguity_low"],
                "ambiguityMedium": attributes["ambiguity_medium"],
                "ambiguityHigh": attributes["ambiguity_high"],
                "radius": round(
                    8.0 + 9.0 * math.sqrt(attributes["strength"] / size_denominator),
                    2,
                ),
                "position": positions[node],
            }
        )

    edges = []
    for source, target, attributes in sorted(
        graph.edges(data=True),
        key=lambda edge: (
            -edge[2]["weight"],
            graph.nodes[edge[0]]["canonical_name"].casefold(),
            graph.nodes[edge[1]]["canonical_name"].casefold(),
        ),
    ):
        edges.append(
            {
                "source": source,
                "target": target,
                "weight": attributes["weight"],
                "documentCount": attributes["document_count"],
                "categoryPair": attributes["category_pair"],
                "evidence": evidence.edge_references.get(
                    _edge_key(source, target), []
                ),
            }
        )

    return {
        "scope": data.scope,
        "networkLabel": f"G{data.minimum_weight}",
        "networkTitle": _network_title(data.minimum_weight),
        "includesIsolates": data.includes_isolates,
        "minimumWeight": data.minimum_weight,
        "maximumWeight": max(
            (attributes["weight"] for _, _, attributes in graph.edges(data=True)),
            default=data.minimum_weight,
        ),
        "nodeCount": graph.number_of_nodes(),
        "edgeCount": graph.number_of_edges(),
        "componentCount": nx.number_connected_components(graph),
        "categoryOrder": list(data.node_categories),
        "categoryPairs": list(data.category_pairs),
        "styles": CATEGORY_STYLE,
        "sentencesByKey": evidence.sentences,
        "nodes": nodes,
        "edges": edges,
    }


def _network_title(minimum_weight: int) -> str:
    if minimum_weight == 1:
        return "G₁ · Red completa de coocurrencia"
    if minimum_weight == 3:
        return "G₃ · Núcleo recurrente de coocurrencia"
    return f"G{minimum_weight} · Red de coocurrencia"


def write_interactive_html(path: Path, payload: dict[str, Any]) -> None:
    serialized = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    html = INTERACTIVE_HTML.replace("__NETWORK_DATA__", serialized)
    path.write_text(html, encoding="utf-8")


def _write_csv(
    path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_filtered_data(
    data: NetworkData,
    output_dir: Path,
    evidence: NetworkEvidence,
) -> dict[str, Any]:
    graph = data.graph
    output_dir.mkdir(parents=True, exist_ok=True)
    network_slug = f"g{data.minimum_weight}"

    node_fields = (
        "canonical_id",
        "canonical_name",
        "category",
        "matrix_index",
        "mention_count",
        "sentence_count",
        "degree",
        "strength",
        "component",
        "component_size",
        "ambiguity_low",
        "ambiguity_medium",
        "ambiguity_high",
    )
    _write_csv(
        output_dir / f"{network_slug}_nodes.csv",
        node_fields,
        (
            {field: graph.nodes[node].get(field, "") for field in node_fields}
            for node in sorted(
                graph,
                key=lambda item: (
                    graph.nodes[item]["component"],
                    CATEGORY_ORDER.index(graph.nodes[item]["category"]),
                    graph.nodes[item]["canonical_name"].casefold(),
                ),
            )
        ),
    )

    edge_fields = (
        "source_canonical_id",
        "target_canonical_id",
        "source_name",
        "target_name",
        "source_category",
        "target_category",
        "category_pair",
        "sentence_count",
        "document_count",
        "evidence_count",
    )
    edge_rows = []
    for source, target, attributes in sorted(
        graph.edges(data=True), key=lambda edge: -edge[2]["weight"]
    ):
        edge_rows.append(
            {
                "source_canonical_id": source,
                "target_canonical_id": target,
                "source_name": graph.nodes[source]["canonical_name"],
                "target_name": graph.nodes[target]["canonical_name"],
                "source_category": graph.nodes[source]["category"],
                "target_category": graph.nodes[target]["category"],
                "category_pair": attributes["category_pair"],
                "sentence_count": attributes["weight"],
                "document_count": attributes["document_count"],
                "evidence_count": len(
                    evidence.edge_references.get(_edge_key(source, target), [])
                ),
            }
        )
    _write_csv(output_dir / f"{network_slug}_edges.csv", edge_fields, edge_rows)

    graph_for_export = nx.Graph()
    graph_for_export.graph.update(
        {
            "scope": data.scope,
            "minimum_weight": data.minimum_weight,
            "edge_definition": "same_sentence_cooccurrence",
            "node_categories": ",".join(data.node_categories),
            "category_pairs": ",".join(data.category_pairs),
        }
    )
    for node, attributes in graph.nodes(data=True):
        graph_for_export.add_node(node, **attributes)
    for source, target, attributes in graph.edges(data=True):
        graph_for_export.add_edge(
            source,
            target,
            edge_key="::".join(_edge_key(source, target)),
            **attributes,
        )
    nx.write_graphml(graph_for_export, output_dir / f"{network_slug}.graphml")

    category_counts = _category_counts(graph)
    category_pair_counts = Counter(
        attributes["category_pair"] for _, _, attributes in graph.edges(data=True)
    )
    components = _ordered_components(graph)
    top_nodes = sorted(
        (
            {
                "canonical_id": node,
                "canonical_name": graph.nodes[node]["canonical_name"],
                "category": graph.nodes[node]["category"],
                "degree": graph.nodes[node]["degree"],
                "strength": graph.nodes[node]["strength"],
            }
            for node in graph
        ),
        key=lambda row: (-row["strength"], -row["degree"], row["canonical_name"]),
    )
    summary = {
        "scope": data.scope,
        "network": f"G{data.minimum_weight}",
        "minimum_edge_weight": data.minimum_weight,
        "includes_isolates": data.includes_isolates,
        "projection": {
            "node_categories": list(data.node_categories),
            "category_pairs": list(data.category_pairs),
        },
        "definition": (
            "Red con todas las aristas cuyo sentence_count >= umbral; "
            "incluye nodos aislados"
            if data.includes_isolates
            else "Subgrafo inducido por aristas con sentence_count >= umbral"
        ),
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "components": len(components),
        "component_sizes": [len(component) for component in components],
        "nodes_by_category": {
            category: category_counts[category] for category in data.node_categories
        },
        "edges_by_category_pair": dict(sorted(category_pair_counts.items())),
        "top_nodes_by_strength": top_nodes[:10],
        "outputs": {
            "free_png": f"{network_slug}_free.png",
            "free_svg": f"{network_slug}_free.svg",
            "interactive_html": f"{network_slug}_interactive.html",
            "graph_json": f"{network_slug}_graph.json",
            "graphml": f"{network_slug}.graphml",
            "nodes_csv": f"{network_slug}_nodes.csv",
            "edges_csv": f"{network_slug}_edges.csv",
        },
    }
    with (output_dir / f"{network_slug}_summary.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return summary


def generate_visualizations(
    analysis_dir: Path,
    output_dir: Path,
    *,
    minimum_weight: int = 3,
    seed: int = 42,
    include_isolates: bool = False,
    node_categories: Sequence[str] | None = None,
    allowed_category_pairs: Sequence[str] | None = None,
) -> dict[str, Any]:
    data = load_core_network(
        analysis_dir,
        minimum_weight,
        include_isolates=include_isolates,
        node_categories=node_categories,
        allowed_category_pairs=allowed_category_pairs,
    )
    graph = data.graph
    free_positions = build_free_layout(graph, seed)
    evidence = load_edge_evidence(analysis_dir, graph)

    network_slug = f"g{minimum_weight}"
    title = _network_title(minimum_weight)
    is_large_network = graph.number_of_nodes() > 80
    label_limit = 25 if is_large_network else None
    subtitle = (
        f"{graph.number_of_nodes()} nodos · {graph.number_of_edges()} aristas · "
        f"{nx.number_connected_components(graph)} componentes · peso ≥ {minimum_weight}"
        + (" · incluye aislados" if include_isolates else "")
        + (" · etiquetas: top 25 por fuerza" if is_large_network else "")
    )
    _draw_graph(
        graph,
        free_positions,
        output_dir / f"{network_slug}_free",
        title=f"{title} · Disposición libre por fuerzas",
        subtitle=subtitle,
        minimum_weight=minimum_weight,
        category_order=data.node_categories,
        label_limit=label_limit,
        show_edge_labels=not is_large_network,
    )

    free_svg_positions = _normalize_for_svg(free_positions)
    payload = _interactive_payload(data, free_svg_positions, evidence)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_interactive_html(output_dir / f"{network_slug}_interactive.html", payload)
    with (output_dir / f"{network_slug}_graph.json").open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))
        file.write("\n")
    return export_filtered_data(data, output_dir, evidence)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera visualizaciones de una red de coocurrencia."
    )
    parser.add_argument(
        "--analysis-dir",
        required=True,
        type=Path,
        help="Directorio que contiene nodes.csv, edges.csv y evidencias.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directorio de salida; por defecto <analysis-dir>/visualizations/g<umbral>.",
    )
    parser.add_argument("--minimum-weight", type=int, default=3)
    parser.add_argument(
        "--include-isolates",
        action="store_true",
        help="Incluye canónicos sin aristas que alcancen el umbral.",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = (
        args.output_dir
        or args.analysis_dir / "visualizations" / f"g{args.minimum_weight}"
    )
    summary = generate_visualizations(
        args.analysis_dir,
        output_dir,
        minimum_weight=args.minimum_weight,
        seed=args.seed,
        include_isolates=args.include_isolates,
    )
    print(
        json.dumps(
            {
                "network": summary["network"],
                "nodes": summary["nodes"],
                "edges": summary["edges"],
                "components": summary["components"],
                "output_dir": str(output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


INTERACTIVE_HTML = r"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Red de coocurrencia</title>
  <style>
    :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; color: #0f172a; background: #f8fafc; }
    header { padding: 18px 24px 12px; background: white; border-bottom: 1px solid #e2e8f0; }
    h1 { margin: 0 0 4px; font-size: 22px; }
    header p { margin: 0; color: #64748b; font-size: 13px; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 12px 18px; align-items: center; padding: 10px 24px; background: white; border-bottom: 1px solid #e2e8f0; font-size: 13px; }
    .group { display: flex; gap: 7px; align-items: center; }
    button, input { font: inherit; }
    button { border: 1px solid #cbd5e1; background: white; border-radius: 7px; padding: 6px 10px; cursor: pointer; color: #334155; }
    button:hover { border-color: #64748b; }
    .category-filter { display: inline-flex; gap: 4px; align-items: center; padding: 3px 6px; border-radius: 6px; }
    .swatch { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
    #search { width: 190px; padding: 6px 8px; border: 1px solid #cbd5e1; border-radius: 7px; }
    main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; height: calc(100vh - 132px); min-height: 620px; }
    .canvas { min-width: 0; position: relative; background: white; overflow: hidden; }
    svg { width: 100%; height: 100%; display: block; cursor: grab; user-select: none; }
    svg.dragging { cursor: grabbing; }
    .edge { stroke: #64748b; stroke-opacity: .48; }
    .edge-hit { stroke: transparent; stroke-width: 14; cursor: pointer; }
    .selected .edge { stroke: #dc2626; stroke-opacity: .92; }
    .node { cursor: pointer; transition: opacity .15s; }
    .node-shape { stroke: #1e293b; stroke-width: 1.2; }
    .node-label { font-size: 11px; fill: #0f172a; paint-order: stroke; stroke: white; stroke-width: 3px; stroke-linejoin: round; pointer-events: none; text-anchor: middle; }
    .edge-label { font-size: 10px; fill: #475569; paint-order: stroke; stroke: white; stroke-width: 3px; pointer-events: none; text-anchor: middle; }
    .dimmed { opacity: .12 !important; }
    .hidden { display: none !important; }
    .selected .node-shape { stroke: #dc2626; stroke-width: 3; }
    aside { overflow: auto; padding: 18px; background: #f8fafc; border-left: 1px solid #e2e8f0; }
    aside h2 { margin: 0 0 10px; font-size: 17px; }
    aside h3 { font-size: 14px; margin: 18px 0 8px; }
    aside p, aside li { font-size: 13px; line-height: 1.45; }
    .meta { display: grid; grid-template-columns: 1fr auto; gap: 6px 10px; font-size: 12px; }
    .meta dt { color: #64748b; }
    .meta dd { margin: 0; font-weight: 600; text-align: right; }
    .evidence { padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; background: white; margin-bottom: 9px; }
    .evidence code { color: #64748b; font-size: 10px; }
    .legend-note { color: #64748b; }
    .tooltip { position: fixed; pointer-events: none; display: none; padding: 6px 8px; border-radius: 6px; color: white; background: rgba(15,23,42,.92); font-size: 12px; z-index: 20; max-width: 280px; }
    @media (max-width: 900px) { main { grid-template-columns: 1fr; height: auto; } .canvas { height: 620px; } aside { border-left: 0; border-top: 1px solid #e2e8f0; } }
  </style>
</head>
<body>
  <header>
    <h1 id="network-title">Red de coocurrencia</h1>
    <p id="subtitle"></p>
  </header>
  <div class="toolbar">
    <div class="group"><label><input id="labels" type="checkbox"> Mostrar etiquetas</label></div>
    <div class="group"><strong>Peso mínimo</strong><input id="weight" type="range"><span id="weight-value"></span></div>
    <div class="group" id="categories"><strong>Categorías</strong></div>
    <div class="group"><input id="search" type="search" placeholder="Buscar entidad…"><button id="reset">Restablecer vista</button></div>
  </div>
  <main>
    <section class="canvas"><svg id="network" viewBox="0 0 1200 780" aria-label="Red de coocurrencia"></svg></section>
    <aside id="details">
      <h2>Guía de lectura</h2>
      <p>Selecciona un nodo o una arista. Una arista indica coocurrencia en una misma oración; su peso es el número de oraciones distintas.</p>
      <p class="legend-note">La red es no dirigida: la posición origen/destino no expresa causalidad ni una relación semántica.</p>
    </aside>
  </main>
  <div class="tooltip" id="tooltip"></div>
  <script>
    const DATA = __NETWORK_DATA__;
    const svg = document.getElementById('network');
    const details = document.getElementById('details');
    const tooltip = document.getElementById('tooltip');
    const nodeById = new Map(DATA.nodes.map(node => [node.id, node]));
    const visibleCategories = new Set(DATA.categoryOrder);
    let selected = null;
    let showLabels = DATA.nodeCount <= 80;
    let viewBox = {x: 0, y: 0, w: 1200, h: 780};

    document.title = DATA.networkTitle;
    document.getElementById('network-title').textContent = DATA.networkTitle;
    document.getElementById('subtitle').textContent = `${DATA.nodeCount} nodos · ${DATA.edgeCount} aristas · ${DATA.componentCount} componentes · peso ≥ ${DATA.minimumWeight}${DATA.includesIsolates ? ' · incluye aislados' : ''}`;
    document.getElementById('labels').checked = showLabels;
    const weightInput = document.getElementById('weight');
    weightInput.min = DATA.minimumWeight;
    weightInput.max = DATA.maximumWeight;
    weightInput.value = DATA.minimumWeight;
    document.getElementById('weight-value').textContent = `≥ ${DATA.minimumWeight}`;

    const counts = Object.fromEntries(DATA.categoryOrder.map(c => [c, DATA.nodes.filter(n => n.category === c).length]));
    const categories = document.getElementById('categories');
    DATA.categoryOrder.forEach(category => {
      const label = document.createElement('label');
      label.className = 'category-filter';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox'; checkbox.checked = true; checkbox.disabled = counts[category] === 0;
      checkbox.addEventListener('change', () => { checkbox.checked ? visibleCategories.add(category) : visibleCategories.delete(category); applyFilters(); });
      const swatch = document.createElement('span'); swatch.className = 'swatch'; swatch.style.background = DATA.styles[category].color;
      label.append(checkbox, swatch, document.createTextNode(`${category} (${counts[category]})`));
      categories.appendChild(label);
    });

    const NS = 'http://www.w3.org/2000/svg';
    const make = (tag, attrs = {}) => { const element = document.createElementNS(NS, tag); Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value)); return element; };
    const edgeGroup = make('g');
    const labelGroup = make('g');
    const nodeGroup = make('g');
    svg.append(edgeGroup, labelGroup, nodeGroup);

    function shapeFor(node) {
      const color = DATA.styles[node.category].color;
      let shape;
      if (node.category === 'CHAR') shape = make('circle', {r: node.radius});
      else if (node.category === 'PRAC') shape = make('rect', {x: -node.radius, y: -node.radius, width: node.radius*2, height: node.radius*2, rx: 3});
      else if (node.category === 'INFRA') shape = make('polygon', {points: `0,${-node.radius} ${node.radius},0 0,${node.radius} ${-node.radius},0`});
      else if (node.category === 'GOV') shape = make('polygon', {points: `0,${-node.radius} ${node.radius*.95},${-node.radius*.3} ${node.radius*.6},${node.radius} ${-node.radius*.6},${node.radius} ${-node.radius*.95},${-node.radius*.3}`});
      else { const r=node.radius; shape=make('polygon',{points:`${-r*.87},${-r*.5} 0,${-r} ${r*.87},${-r*.5} ${r*.87},${r*.5} 0,${r} ${-r*.87},${r*.5}`}); }
      shape.setAttribute('fill', color); shape.setAttribute('class','node-shape');
      return shape;
    }

    const edgeElements = DATA.edges.map((edge, index) => {
      const group = make('g', {'data-index': index});
      const line = make('line', {class:'edge'});
      line.style.strokeWidth = `${1 + .9*Math.sqrt(edge.weight-DATA.minimumWeight+1)}px`;
      const hit = make('line', {class:'edge-hit'});
      const label = make('text', {class:'edge-label'}); label.textContent = edge.weight;
      hit.addEventListener('click', event => { event.stopPropagation(); selectEdge(edge, group); });
      hit.addEventListener('mousemove', event => showTooltip(event, `${nodeById.get(edge.source).name} — ${nodeById.get(edge.target).name}<br>Peso: ${edge.weight}`));
      hit.addEventListener('mouseleave', hideTooltip);
      group.append(line, hit); labelGroup.appendChild(label); edgeGroup.appendChild(group);
      return {edge, group, line, hit, label};
    });

    const nodeElements = DATA.nodes.map(node => {
      const group = make('g', {class:'node', tabindex:'0'});
      group.appendChild(shapeFor(node));
      const label = make('text', {class:'node-label', y: node.radius+15});
      label.textContent = node.name.length > 28 ? `${node.name.slice(0,26)}…` : node.name;
      group.appendChild(label); nodeGroup.appendChild(group);
      group.addEventListener('click', event => { event.stopPropagation(); selectNode(node, group); });
      group.addEventListener('mousemove', event => showTooltip(event, `<strong>${escapeHtml(node.name)}</strong><br>${node.category} · grado ${node.degree} · fuerza ${node.strength}`));
      group.addEventListener('mouseleave', hideTooltip);
      return {node, group, label};
    });

    function updatePositions() {
      nodeElements.forEach(({node,group}) => { const p=node.position; group.setAttribute('transform',`translate(${p.x},${p.y})`); });
      edgeElements.forEach(item => {
        const a=nodeById.get(item.edge.source).position, b=nodeById.get(item.edge.target).position;
        [item.line,item.hit].forEach(line => { line.setAttribute('x1',a.x); line.setAttribute('y1',a.y); line.setAttribute('x2',b.x); line.setAttribute('y2',b.y); });
        item.label.setAttribute('x',(a.x+b.x)/2); item.label.setAttribute('y',(a.y+b.y)/2-5);
      });
      applyFilters();
    }

    function applyFilters() {
      const minimum = Number(weightInput.value);
      const query = document.getElementById('search').value.trim().toLocaleLowerCase('es');
      const visibleNodes = new Set(DATA.nodes.filter(node => visibleCategories.has(node.category)).map(node => node.id));
      nodeElements.forEach(({node,group,label}) => {
        group.classList.toggle('hidden',!visibleNodes.has(node.id));
        group.classList.toggle('dimmed',Boolean(query) && !node.name.toLocaleLowerCase('es').includes(query));
        label.classList.toggle('hidden', !showLabels);
      });
      edgeElements.forEach(({edge,group,label}) => {
        const hidden = edge.weight < minimum || !visibleNodes.has(edge.source) || !visibleNodes.has(edge.target);
        group.classList.toggle('hidden',hidden); label.classList.toggle('hidden',hidden || DATA.nodeCount > 80);
      });
      document.getElementById('weight-value').textContent = `≥ ${minimum}`;
    }

    const escapeHtml = value => String(value).replace(/[&<>"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[char]));
    function clearSelection() { document.querySelectorAll('.selected').forEach(element => element.classList.remove('selected')); selected=null; }
    function selectNode(node, group) {
      clearSelection(); group.classList.add('selected'); selected=node.id;
      const neighbors = DATA.edges.filter(edge => edge.source===node.id || edge.target===node.id).sort((a,b)=>b.weight-a.weight).map(edge => { const other=nodeById.get(edge.source===node.id?edge.target:edge.source); return `<li><strong>${escapeHtml(other.name)}</strong> (${other.category}) · peso ${edge.weight}</li>`; }).join('');
      details.innerHTML = `<h2>${escapeHtml(node.name)}</h2><dl class="meta"><dt>Categoría</dt><dd>${node.category}</dd><dt>Componente</dt><dd>${node.component}</dd><dt>Grado</dt><dd>${node.degree}</dd><dt>Fuerza</dt><dd>${node.strength}</dd><dt>Menciones</dt><dd>${node.mentionCount}</dd><dt>Oraciones</dt><dd>${node.sentenceCount}</dd></dl><h3>Vecinos en ${DATA.networkLabel}</h3><ul>${neighbors}</ul><h3>Identificador canónico</h3><p><code>${escapeHtml(node.id)}</code></p>`;
    }
    function selectEdge(edge, group) {
      clearSelection(); group.classList.add('selected');
      const source=nodeById.get(edge.source), target=nodeById.get(edge.target);
      const evidence=edge.evidence.map(item=>{
        const sentence=DATA.sentencesByKey[item.sentenceKey] || {};
        const entities=(sentence.contextEntities || []).map(entity=>`${escapeHtml(entity.canonicalName)} <small>(${escapeHtml(entity.category)})</small>`).join(' · ');
        return `<article class="evidence"><code>Documento: ${escapeHtml(sentence.documentId || '')}<br>Oración: ${escapeHtml(sentence.sentenceId || '')}</code><p>${escapeHtml(sentence.context || item.pairContext || '')}</p><p><strong>Entidades:</strong> ${entities || 'Sin entidades exportadas'}</p></article>`;
      }).join('');
      details.innerHTML=`<h2>${escapeHtml(source.name)} — ${escapeHtml(target.name)}</h2><dl class="meta"><dt>category_pair</dt><dd>${escapeHtml(edge.categoryPair)}</dd><dt>Peso</dt><dd>${edge.weight} oraciones</dd><dt>Documentos</dt><dd>${edge.documentCount}</dd><dt>Dirección</dt><dd>No dirigida</dd></dl><h3>Evidencia textual (${edge.evidence.length})</h3>${evidence || '<p>No se encontró evidencia exportada.</p>'}`;
    }
    function showTooltip(event, html) { tooltip.innerHTML=html; tooltip.style.display='block'; tooltip.style.left=`${event.clientX+12}px`; tooltip.style.top=`${event.clientY+12}px`; }
    function hideTooltip(){ tooltip.style.display='none'; }
    function setViewBox(){ svg.setAttribute('viewBox',`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`); }
    function resetView(){ viewBox={x:0,y:0,w:1200,h:780}; setViewBox(); clearSelection(); }

    document.getElementById('labels').addEventListener('change', event=>{showLabels=event.target.checked; applyFilters();});
    weightInput.addEventListener('input',applyFilters);
    document.getElementById('search').addEventListener('input',applyFilters);
    document.getElementById('reset').addEventListener('click',resetView);
    svg.addEventListener('click',()=>clearSelection());
    svg.addEventListener('wheel',event=>{event.preventDefault(); const factor=event.deltaY>0?1.12:.89; const rect=svg.getBoundingClientRect(); const px=viewBox.x+(event.clientX-rect.left)/rect.width*viewBox.w; const py=viewBox.y+(event.clientY-rect.top)/rect.height*viewBox.h; viewBox.x=px-(px-viewBox.x)*factor; viewBox.y=py-(py-viewBox.y)*factor; viewBox.w*=factor; viewBox.h*=factor; setViewBox();},{passive:false});
    let drag=null;
    svg.addEventListener('mousedown',event=>{if(event.target.closest('.node')||event.target.closest('.edge-hit'))return; drag={x:event.clientX,y:event.clientY,vx:viewBox.x,vy:viewBox.y}; svg.classList.add('dragging');});
    window.addEventListener('mousemove',event=>{if(!drag)return; const rect=svg.getBoundingClientRect(); viewBox.x=drag.vx-(event.clientX-drag.x)/rect.width*viewBox.w; viewBox.y=drag.vy-(event.clientY-drag.y)/rect.height*viewBox.h; setViewBox();});
    window.addEventListener('mouseup',()=>{drag=null;svg.classList.remove('dragging');});
    updatePositions();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
