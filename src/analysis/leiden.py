"""Detección reproducible de comunidades Leiden sobre GraphML existentes.

El módulo no construye ni modifica la red de evidencia. Lee un GraphML ya
versionado, calcula una partición y exporta un GraphML derivado con atributos
que Gephi puede usar directamente para colorear comunidades.
"""

from __future__ import annotations

import colorsys
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable, Sequence

import networkx as nx

LEIDEN_METHOD = "leiden-v1"
LEIDEN_OBJECTIVES = ("modularity", "cpm")
LEIDEN_WEIGHT_ATTRIBUTES = (
    "none",
    "weight",
    "analysis_weight",
    "sentence_count",
    "document_count",
    "fractional_weight",
    "fractional_document_weight",
)


class LeidenError(ValueError):
    """Error de entrada o topología que impide calcular Leiden."""


class LeidenDependencyError(RuntimeError):
    """La implementación nativa de Leiden no está instalada."""


@dataclass(frozen=True)
class LeidenConfig:
    method: str = LEIDEN_METHOD
    objective_function: str = "modularity"
    resolution: float = 1.0
    seed: int = 42
    iterations: int = -1
    weight_attribute: str = "weight"

    def validate(self) -> None:
        if self.method != LEIDEN_METHOD:
            raise LeidenError(f"Método de clustering no soportado: {self.method}")
        if self.objective_function not in LEIDEN_OBJECTIVES:
            raise LeidenError(
                "objective_function debe ser uno de: " + ", ".join(LEIDEN_OBJECTIVES)
            )
        if not math.isfinite(self.resolution) or self.resolution <= 0:
            raise LeidenError("resolution debe ser un número finito mayor que 0")
        if self.seed < 0 or self.seed > 2_147_483_647:
            raise LeidenError("seed debe estar entre 0 y 2147483647")
        if self.iterations != -1 and self.iterations < 1:
            raise LeidenError("iterations debe ser -1 o un entero mayor que 0")
        if self.weight_attribute not in LEIDEN_WEIGHT_ATTRIBUTES:
            raise LeidenError(
                "weight_attribute debe ser uno de: "
                + ", ".join(LEIDEN_WEIGHT_ATTRIBUTES)
            )


def graph_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(
    path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {"networkx": nx.__version__}
    for package in ("igraph", "leidenalg"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _read_source_graph(path: Path) -> nx.Graph:
    try:
        source = nx.read_graphml(path)
    except Exception as exc:  # pragma: no cover - depende del parser XML
        raise LeidenError(f"No fue posible leer el GraphML fuente: {exc}") from exc
    if source.is_directed():
        raise LeidenError("Leiden v1 solo admite grafos no dirigidos")
    if source.is_multigraph():
        raise LeidenError("Leiden v1 no admite GraphML con aristas paralelas")
    return nx.Graph(source)


def _edge_weight(
    attributes: dict[str, Any], weight_attribute: str, source: Any, target: Any
) -> float:
    if weight_attribute == "none":
        return 1.0
    if weight_attribute not in attributes:
        raise LeidenError(
            f"La arista {source}--{target} no contiene el peso " f"'{weight_attribute}'"
        )
    try:
        value = float(attributes[weight_attribute])
    except (TypeError, ValueError) as exc:
        raise LeidenError(
            f"El peso '{weight_attribute}' de {source}--{target} no es numérico"
        ) from exc
    if not math.isfinite(value) or value <= 0:
        raise LeidenError(
            f"El peso '{weight_attribute}' de {source}--{target} debe ser "
            "finito y mayor que 0"
        )
    return value


def _run_native_leiden(
    graph: nx.Graph,
    config: LeidenConfig,
) -> tuple[list[int], float, float, dict[str, str]]:
    try:
        import igraph as ig
        import leidenalg as la
    except ImportError as exc:  # pragma: no cover - cubierto por integración
        raise LeidenDependencyError(
            "Leiden requiere las dependencias 'igraph' y 'leidenalg'"
        ) from exc

    node_ids = sorted(graph.nodes, key=str)
    node_index = {node: index for index, node in enumerate(node_ids)}
    edge_rows = sorted(
        graph.edges(data=True),
        key=lambda edge: tuple(sorted((node_index[edge[0]], node_index[edge[1]]))),
    )
    igraph_edges = [
        (node_index[source], node_index[target]) for source, target, _ in edge_rows
    ]
    weights = [
        _edge_weight(attributes, config.weight_attribute, source, target)
        for source, target, attributes in edge_rows
    ]
    igraph_graph = ig.Graph(
        n=len(node_ids),
        edges=igraph_edges,
        directed=False,
    )
    partition_type = (
        la.RBConfigurationVertexPartition
        if config.objective_function == "modularity"
        else la.CPMVertexPartition
    )
    partition = la.find_partition(
        igraph_graph,
        partition_type,
        weights=weights if config.weight_attribute != "none" else None,
        resolution_parameter=config.resolution,
        n_iterations=config.iterations,
        seed=config.seed,
    )
    membership_by_node = {
        node: int(partition.membership[index]) for index, node in enumerate(node_ids)
    }
    membership = [membership_by_node[node] for node in graph.nodes]
    classical_modularity = float(
        igraph_graph.modularity(
            partition.membership,
            weights=weights if config.weight_attribute != "none" else None,
            resolution=1.0,
            directed=False,
        )
    )
    return (
        membership,
        float(partition.quality()),
        classical_modularity,
        {
            "igraph": getattr(ig, "__version__", "unknown"),
            "leidenalg": metadata.version("leidenalg"),
            "partition_type": partition_type.__name__,
        },
    )


def _stable_communities(
    graph: nx.Graph, membership: Sequence[int]
) -> tuple[dict[Any, int], list[list[Any]]]:
    raw_communities: dict[int, list[Any]] = defaultdict(list)
    for node, raw_community in zip(graph.nodes, membership, strict=True):
        raw_communities[int(raw_community)].append(node)
    ordered = sorted(
        raw_communities.values(),
        key=lambda members: (
            -len(members),
            tuple(sorted(str(member) for member in members)),
        ),
    )
    class_by_node = {
        node: modularity_class
        for modularity_class, members in enumerate(ordered)
        for node in members
    }
    return class_by_node, ordered


def _community_color(modularity_class: int) -> str:
    # Salto áureo: colores deterministas y razonablemente separados entre vecinos.
    hue = (0.61803398875 * modularity_class + 0.08) % 1.0
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.68, 0.88)
    return f"#{round(red * 255):02X}{round(green * 255):02X}{round(blue * 255):02X}"


def _annotate_communities(
    graph: nx.Graph,
    class_by_node: dict[Any, int],
    communities: Sequence[Sequence[Any]],
) -> nx.Graph:
    annotated = graph.copy()
    for node in annotated.nodes:
        modularity_class = class_by_node[node]
        size = len(communities[modularity_class])
        annotated.nodes[node].update(
            {
                "modularity_class": modularity_class,
                "community_id": f"C{modularity_class + 1:03d}",
                "community_rank": modularity_class + 1,
                "community_size": size,
                "community_is_singleton": size == 1,
                "community_color": _community_color(modularity_class),
            }
        )
    return annotated


def _community_rows(
    graph: nx.Graph,
    communities: Sequence[Sequence[Any]],
    config: LeidenConfig,
) -> list[dict[str, Any]]:
    class_by_node = {
        node: modularity_class
        for modularity_class, members in enumerate(communities)
        for node in members
    }
    internal_edges: Counter[int] = Counter()
    boundary_edges: Counter[int] = Counter()
    internal_weights: Counter[int] = Counter()
    boundary_weights: Counter[int] = Counter()
    for source, target, attributes in graph.edges(data=True):
        source_class = class_by_node[source]
        target_class = class_by_node[target]
        weight = _edge_weight(attributes, config.weight_attribute, source, target)
        if source_class == target_class:
            internal_edges[source_class] += 1
            internal_weights[source_class] += weight
        else:
            boundary_edges[source_class] += 1
            boundary_edges[target_class] += 1
            boundary_weights[source_class] += weight
            boundary_weights[target_class] += weight

    rows: list[dict[str, Any]] = []
    for modularity_class, members in enumerate(communities):
        categories = Counter(
            str(graph.nodes[node].get("category", "UNKNOWN")) for node in members
        )
        possible_edges = len(members) * (len(members) - 1) / 2
        top_members = sorted(
            members,
            key=lambda node: (
                -float(graph.nodes[node].get("strength", graph.degree(node))),
                str(
                    graph.nodes[node].get(
                        "canonical_name", graph.nodes[node].get("label", node)
                    )
                ).casefold(),
            ),
        )[:10]
        component_ids = sorted(
            {
                str(graph.nodes[node].get("component", ""))
                for node in members
                if graph.nodes[node].get("component", "") != ""
            }
        )
        rows.append(
            {
                "modularity_class": modularity_class,
                "community_id": f"C{modularity_class + 1:03d}",
                "community_rank": modularity_class + 1,
                "community_color": _community_color(modularity_class),
                "node_count": len(members),
                "category_count": len(categories),
                "category_profile": ",".join(sorted(categories)),
                "prac_nodes": categories.get("PRAC", 0),
                "infra_nodes": categories.get("INFRA", 0),
                "rul_nodes": categories.get("RUL", 0),
                "category_counts_json": json.dumps(
                    dict(sorted(categories.items())), ensure_ascii=False
                ),
                "internal_edges": internal_edges[modularity_class],
                "boundary_edges": boundary_edges[modularity_class],
                "internal_weight": round(internal_weights[modularity_class], 12),
                "boundary_weight": round(boundary_weights[modularity_class], 12),
                "internal_density": round(
                    (
                        internal_edges[modularity_class] / possible_edges
                        if possible_edges
                        else 0.0
                    ),
                    12,
                ),
                "component_ids": ",".join(component_ids),
                "is_singleton": len(members) == 1,
                "top_members": " | ".join(
                    str(
                        graph.nodes[node].get(
                            "canonical_name", graph.nodes[node].get("label", node)
                        )
                    )
                    for node in top_members
                ),
            }
        )
    return rows


COMMUNITY_FIELDS = (
    "modularity_class",
    "community_id",
    "community_rank",
    "community_color",
    "node_count",
    "category_count",
    "category_profile",
    "prac_nodes",
    "infra_nodes",
    "rul_nodes",
    "category_counts_json",
    "internal_edges",
    "boundary_edges",
    "internal_weight",
    "boundary_weight",
    "internal_density",
    "component_ids",
    "is_singleton",
    "top_members",
)


def _member_rows(graph: nx.Graph) -> tuple[list[str], list[dict[str, Any]]]:
    preferred_fields = [
        "canonical_id",
        "canonical_name",
        "label",
        "category",
        "modularity_class",
        "community_id",
        "community_rank",
        "community_size",
        "community_is_singleton",
        "community_color",
        "component",
        "component_size",
        "degree",
        "strength",
        "document_count",
        "sentence_count",
        "mention_count",
    ]
    available = {
        str(field) for _, attributes in graph.nodes(data=True) for field in attributes
    }
    fields = [field for field in preferred_fields if field in available]
    fields.extend(sorted(available - set(fields)))
    rows = []
    for node, attributes in sorted(
        graph.nodes(data=True),
        key=lambda item: (
            int(item[1]["modularity_class"]),
            str(
                item[1].get("canonical_name", item[1].get("label", item[0]))
            ).casefold(),
            str(item[0]),
        ),
    ):
        row = {field: attributes.get(field, "") for field in fields}
        if "canonical_id" in fields and not row["canonical_id"]:
            row["canonical_id"] = str(node)
        rows.append(row)
    return fields, rows


def export_leiden_clustering(
    source_graphml: Path,
    output_dir: Path,
    *,
    config: LeidenConfig,
    base_name: str = "network_clustered",
) -> dict[str, Any]:
    """Calcula Leiden y exporta artefactos derivados, sin tocar el GraphML fuente."""

    config.validate()
    source_hash = graph_file_sha256(source_graphml)
    graph = _read_source_graph(source_graphml)
    # Validar pesos antes de cargar las dependencias opcionales permite devolver
    # un 422 determinista aun cuando Leiden no esté instalado en este entorno.
    for source, target, attributes in graph.edges(data=True):
        _edge_weight(attributes, config.weight_attribute, source, target)
    warnings: list[str] = []
    algorithm_versions = _dependency_versions()

    if graph.number_of_nodes() == 0:
        membership: list[int] = []
        objective_quality = 0.0
        modularity = 0.0
        status = "empty"
        warnings.append("El GraphML fuente no contiene nodos")
    elif graph.number_of_edges() == 0:
        membership = list(range(graph.number_of_nodes()))
        objective_quality = 0.0
        modularity = 0.0
        status = "trivial"
        warnings.append(
            "El GraphML fuente no contiene aristas; cada nodo se exportó como singleton"
        )
    else:
        (
            membership,
            objective_quality,
            modularity,
            native_versions,
        ) = _run_native_leiden(graph, config)
        algorithm_versions.update(native_versions)
        status = "completed"

    class_by_node, communities = _stable_communities(graph, membership)
    clustered_graph = _annotate_communities(graph, class_by_node, communities)
    community_rows = _community_rows(clustered_graph, communities, config)
    generated_at = datetime.now(timezone.utc).isoformat()
    clustered_graph.graph.update(
        {
            "clustering_method": config.method,
            "clustering_objective_function": config.objective_function,
            "clustering_resolution": config.resolution,
            "clustering_seed": config.seed,
            "clustering_iterations": config.iterations,
            "clustering_weight_attribute": config.weight_attribute,
            "clustering_status": status,
            "clustering_community_count": len(communities),
            "clustering_objective_quality": round(objective_quality, 12),
            "clustering_modularity": round(modularity, 12),
            "clustering_generated_at": generated_at,
            "source_graph_sha256": source_hash,
        }
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    clustered_graphml_path = output_dir / f"{base_name}.graphml"
    communities_path = output_dir / f"{base_name}_communities.csv"
    members_path = output_dir / f"{base_name}_members.csv"
    summary_path = output_dir / f"{base_name}.json"
    nx.write_graphml(clustered_graph, clustered_graphml_path)
    _write_csv(communities_path, COMMUNITY_FIELDS, community_rows)
    member_fields, member_rows = _member_rows(clustered_graph)
    _write_csv(members_path, member_fields, member_rows)

    community_sizes = [len(members) for members in communities]
    payload = {
        "generated_at": generated_at,
        "status": status,
        "cached": False,
        "configuration": asdict(config),
        "algorithm_versions": algorithm_versions,
        "source": {
            "graphml_sha256": source_hash,
            "canonical_nodes": graph.number_of_nodes(),
            "undirected_edges": graph.number_of_edges(),
        },
        "counts": {
            "communities": len(communities),
            "singleton_communities": sum(
                1 for members in communities if len(members) == 1
            ),
            "largest_community_size": max(community_sizes, default=0),
            "smallest_community_size": min(community_sizes, default=0),
        },
        "community_sizes": community_sizes,
        "objective_quality": round(objective_quality, 12),
        "modularity": round(modularity, 12),
        "definitions": {
            "modularity_class": (
                "stable zero-based community index for Gephi partition coloring"
            ),
            "community_id": "stable rank C001..Cn within this exact partition",
            "objective_quality": "native quality optimized by the Leiden partition",
            "modularity": "classical weighted modularity at resolution 1.0",
        },
        "warnings": warnings,
        "outputs": {
            "clustered_graphml": clustered_graphml_path.name,
            "communities_csv": communities_path.name,
            "community_members_csv": members_path.name,
            "clustering_summary_json": summary_path.name,
        },
    }
    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return payload
