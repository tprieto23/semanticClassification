"""Red de entidades filtrable para el explorador interactivo.

El módulo no consulta ni modifica PostgreSQL. Recibe menciones ya
canonicalizadas, reutiliza la coocurrencia por oración y el núcleo de
recurrencia documental, y devuelve una red legible acompañada de sus métricas.

Los filtros se aplican en un orden fijo y cada etapa queda contabilizada:

1. categorías de nodos y tipos de link permitidos;
2. recurrencia documental de nodos (``document-recurrent-core-v1``);
3. peso analítico mínimo de arista;
4. métricas de centralidad sobre la red filtrada completa;
5. selección de los ``top_n`` nodos por la métrica elegida.

Las métricas se calculan antes del recorte del paso 5, de modo que la posición
de un nodo no depende de cuántos nodos se dibujen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

import networkx as nx

from src.analysis.backbone import (
    DocumentRecurrentCoreConfig,
    build_document_recurrent_core,
)
from src.analysis.cooccurrence import (
    CATEGORY_RANK,
    MentionRecord,
    all_category_pairs,
    build_sentence_cooccurrence,
    ordered_category_pair,
)
from src.categories import ACTIVE_CATEGORIES, LEGACY_CATEGORIES

EXPLORER_VERSION = "entity-explorer-v1"

LinkMode = Literal["any", "between", "within", "pairs"]
RankingMetric = Literal[
    "pagerank",
    "degree",
    "strength",
    "betweenness",
    "closeness",
    "document_count",
]
RANKING_METRICS: tuple[str, ...] = (
    "pagerank",
    "degree",
    "strength",
    "betweenness",
    "closeness",
    "document_count",
)

# Períodos de análisis acordados para la evolución temporal.
PERIODS: tuple[dict[str, Any], ...] = (
    {"id": "2021-2023", "label": "2021–2023", "year_from": 2021, "year_to": 2023},
    {"id": "2024-2026", "label": "2024–2026", "year_from": 2024, "year_to": 2026},
)
PERIODS_BY_ID = {period["id"]: period for period in PERIODS}

CATEGORY_LABELS = {
    "CHAR": "Actores",
    "KNOW": "Saberes",
    "ATT": "Actitudes y valores",
    "SKILL": "Habilidades",
    "PRAC": "Prácticas",
    "physical_INFRA": "Infraestructura física",
    "soft_INFRA": "Infraestructura de soporte",
    "eco_INFRA": "Infraestructura ecológica",
    "RUL": "Reglas",
    "LOC": "Lugares",
    "INFRA": "Infraestructura (legado)",
}

# Por encima de este tamaño, betweenness se estima con una muestra fija de
# fuentes para que la respuesta siga siendo interactiva.
EXACT_BETWEENNESS_MAX_NODES = 1500
BETWEENNESS_SAMPLE_SIZE = 500
METRIC_SEED = 42


class ExplorerFilterError(ValueError):
    """Combinación de filtros imposible de construir."""


@dataclass(frozen=True)
class ExplorerFilters:
    categories: tuple[str, ...] | None = None
    link_mode: LinkMode = "any"
    category_pairs: tuple[tuple[str, str], ...] | None = None
    minimum_node_document_count: int = 2
    edge_weighting: str = "fractional-document"
    minimum_edge_weight: float = 0.0
    ranking_metric: RankingMetric = "pagerank"
    top_n: int | None = 150


def resolve_categories(
    requested: Sequence[str] | None,
    mentions: Sequence[MentionRecord],
) -> tuple[str, ...]:
    """Categorías de nodos; por defecto, las diez activas y el legado presente."""

    if requested:
        unknown = sorted(set(requested) - ACTIVE_CATEGORIES - LEGACY_CATEGORIES)
        if unknown:
            raise ExplorerFilterError("Categorías no permitidas: " + ", ".join(unknown))
        selected = set(requested)
    else:
        legacy_present = {mention.category for mention in mentions} & LEGACY_CATEGORIES
        selected = set(ACTIVE_CATEGORIES) | legacy_present
    return tuple(sorted(selected, key=lambda category: CATEGORY_RANK[category]))


def resolve_category_pairs(
    categories: Sequence[str],
    link_mode: LinkMode,
    category_pairs: Sequence[tuple[str, str]] | None = None,
) -> tuple[tuple[str, str], ...]:
    """Traduce el modo de link a la lista de pares no dirigidos permitidos."""

    every_pair = all_category_pairs(categories)
    if link_mode == "any":
        pairs = every_pair
    elif link_mode == "between":
        pairs = tuple(pair for pair in every_pair if pair[0] != pair[1])
    elif link_mode == "within":
        pairs = tuple(pair for pair in every_pair if pair[0] == pair[1])
    elif link_mode == "pairs":
        if not category_pairs:
            raise ExplorerFilterError(
                "link_mode='pairs' requiere al menos un category_pair"
            )
        selected = set(categories)
        outside = [
            f"{source}--{target}"
            for source, target in category_pairs
            if source not in selected or target not in selected
        ]
        if outside:
            raise ExplorerFilterError(
                "Los category_pairs usan categorías no seleccionadas: "
                + ", ".join(outside)
            )
        pairs = tuple(
            sorted(
                {
                    ordered_category_pair(source, target)
                    for source, target in category_pairs
                },
                key=lambda pair: (CATEGORY_RANK[pair[0]], CATEGORY_RANK[pair[1]]),
            )
        )
    else:
        raise ExplorerFilterError(f"link_mode no soportado: {link_mode!r}")

    if not pairs:
        raise ExplorerFilterError(
            "La combinación de categorías y link_mode no permite ningún link: "
            "'between' necesita al menos dos categorías"
        )
    return pairs


def _distance_graph(graph: nx.Graph) -> nx.Graph:
    """Copia con distancia inversa al peso: un link fuerte acorta el camino."""

    distance_graph = nx.Graph()
    distance_graph.add_nodes_from(graph.nodes)
    for source, target, attributes in graph.edges(data=True):
        weight = float(attributes["analysis_weight"])
        distance_graph.add_edge(source, target, distance=1.0 / weight)
    return distance_graph


def compute_node_metrics(graph: nx.Graph) -> tuple[dict[str, dict[str, float]], dict]:
    """Calcula centralidades ponderadas y devuelve también su procedencia."""

    if graph.number_of_nodes() == 0:
        return {}, {"betweenness": "exact", "betweenness_sample_size": None}

    distance_graph = _distance_graph(graph)
    pagerank = nx.pagerank(graph, weight="analysis_weight")
    closeness = nx.closeness_centrality(distance_graph, distance="distance")

    node_count = graph.number_of_nodes()
    if node_count > EXACT_BETWEENNESS_MAX_NODES:
        sample_size = min(BETWEENNESS_SAMPLE_SIZE, node_count)
        betweenness = nx.betweenness_centrality(
            distance_graph,
            k=sample_size,
            weight="distance",
            normalized=True,
            seed=METRIC_SEED,
        )
        provenance = {"betweenness": "sampled", "betweenness_sample_size": sample_size}
    else:
        betweenness = nx.betweenness_centrality(
            distance_graph, weight="distance", normalized=True
        )
        provenance = {"betweenness": "exact", "betweenness_sample_size": None}

    metrics: dict[str, dict[str, float]] = {}
    for node in graph:
        metrics[node] = {
            "degree": graph.degree(node),
            "strength": round(
                sum(
                    float(attributes["analysis_weight"])
                    for _, _, attributes in graph.edges(node, data=True)
                ),
                12,
            ),
            "betweenness": round(betweenness[node], 12),
            "closeness": round(closeness[node], 12),
            "pagerank": round(pagerank[node], 12),
            "document_count": graph.nodes[node]["document_count"],
        }
    return metrics, provenance


def rank_nodes(
    graph: nx.Graph,
    metrics: dict[str, dict[str, float]],
    metric: str,
) -> list[str]:
    """Orden descendente por métrica, desempatado de forma reproducible."""

    return sorted(
        graph,
        key=lambda node: (
            -metrics[node][metric],
            -metrics[node]["strength"],
            graph.nodes[node]["canonical_name"].casefold(),
            node,
        ),
    )


def _empty_network(stages: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    return {
        "nodes": [],
        "edges": [],
        "stages": stages,
        "metric_provenance": {"betweenness": "exact", "betweenness_sample_size": None},
        "warnings": warnings,
    }


def build_explorer_network(
    mentions: Sequence[MentionRecord],
    filters: ExplorerFilters,
) -> dict[str, Any]:
    """Construye la red filtrada, sus métricas y el conteo de cada etapa."""

    if filters.ranking_metric not in RANKING_METRICS:
        raise ExplorerFilterError(
            f"ranking_metric no soportada: {filters.ranking_metric!r}"
        )
    categories = resolve_categories(filters.categories, mentions)
    pairs = resolve_category_pairs(
        categories, filters.link_mode, filters.category_pairs
    )
    config = DocumentRecurrentCoreConfig(
        minimum_node_document_count=filters.minimum_node_document_count,
        edge_weighting=filters.edge_weighting,
    )
    try:
        config.validate()
    except ValueError as error:
        raise ExplorerFilterError(str(error)) from error

    stages: dict[str, Any] = {
        "categories": list(categories),
        "category_pairs": ["--".join(pair) for pair in pairs],
        "mentions": len(mentions),
        "cooccurrence": {"nodes": 0, "edges": 0},
        "document_recurrence": {"nodes": 0, "edges": 0},
        "edge_weight": {"nodes": 0, "edges": 0},
        "shown": {"nodes": 0, "edges": 0},
    }
    warnings: list[str] = []

    selected_mentions = [
        mention for mention in mentions if mention.category in categories
    ]
    if not selected_mentions:
        warnings.append(
            "No hay menciones de las categorías seleccionadas en este alcance"
        )
        return _empty_network(stages, warnings)

    result = build_sentence_cooccurrence(
        mentions, node_categories=categories, allowed_category_pairs=pairs
    )
    stages["cooccurrence"] = {
        "nodes": len(result.nodes),
        "edges": len(result.edge_weights),
    }

    core = build_document_recurrent_core(result, config)
    graph = core.graph
    stages["document_recurrence"] = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
    }

    weak_edges = [
        (source, target)
        for source, target, attributes in graph.edges(data=True)
        if float(attributes["analysis_weight"]) < filters.minimum_edge_weight
    ]
    graph = nx.Graph(graph)
    graph.remove_edges_from(weak_edges)
    graph.remove_nodes_from([node for node in list(graph) if graph.degree(node) == 0])
    stages["edge_weight"] = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
    }

    if graph.number_of_nodes() == 0:
        warnings.append(
            "Ningún link supera los filtros de recurrencia y peso; "
            "pruebe bajar minimum_node_document_count o minimum_edge_weight"
        )
        return _empty_network(stages, warnings)

    metrics, provenance = compute_node_metrics(graph)
    ranking = {
        metric: {
            node: index
            for index, node in enumerate(rank_nodes(graph, metrics, metric), start=1)
        }
        for metric in RANKING_METRICS
    }
    ordered = rank_nodes(graph, metrics, filters.ranking_metric)
    shown_ids = ordered if filters.top_n is None else ordered[: filters.top_n]
    shown = graph.subgraph(shown_ids)

    nodes = [
        {
            "id": node,
            "name": graph.nodes[node]["canonical_name"],
            "category": graph.nodes[node]["category"],
            "mention_count": graph.nodes[node]["mention_count"],
            "sentence_count": graph.nodes[node]["sentence_count"],
            "metrics": metrics[node],
            "ranks": {metric: ranking[metric][node] for metric in RANKING_METRICS},
            "shown_degree": shown.degree(node),
        }
        for node in shown_ids
    ]
    edges = [
        {
            "source": source,
            "target": target,
            "weight": attributes["analysis_weight"],
            "sentence_count": attributes["sentence_count"],
            "document_count": attributes["document_count"],
            "category_pair": attributes["category_pair"],
            "confidence_tier": attributes["confidence_tier"],
        }
        for source, target, attributes in sorted(
            shown.edges(data=True),
            key=lambda edge: (-edge[2]["analysis_weight"], edge[0], edge[1]),
        )
    ]
    stages["shown"] = {"nodes": len(nodes), "edges": len(edges)}
    if filters.top_n is not None and len(ordered) > filters.top_n:
        warnings.append(
            f"Se muestran los {filters.top_n} nodos con mayor {filters.ranking_metric} "
            f"de {len(ordered)} que superan los filtros"
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "stages": stages,
        "metric_provenance": provenance,
        "warnings": warnings,
    }


def compare_rankings(
    networks_by_period: dict[str, dict[str, Any]],
    metric: str,
    top_k: int,
) -> dict[str, Any]:
    """Compara el ranking de una métrica entre períodos ordenados.

    Cada red debe haberse construido con los mismos filtros. Los nodos de la
    respuesta son la unión de los ``top_k`` de cada período; para cada uno se
    informa su rango y valor en todos los períodos (``None`` si no superó los
    filtros en ese período).
    """

    if metric not in RANKING_METRICS:
        raise ExplorerFilterError(f"Métrica no soportada: {metric!r}")
    period_ids = list(networks_by_period)

    nodes_by_period: dict[str, dict[str, dict[str, Any]]] = {
        period_id: {node["id"]: node for node in network["nodes"]}
        for period_id, network in networks_by_period.items()
    }
    top_by_period: dict[str, list[str]] = {
        period_id: [
            node["id"]
            for node in sorted(
                network["nodes"], key=lambda node: node["ranks"][metric]
            )[:top_k]
        ]
        for period_id, network in networks_by_period.items()
    }

    tracked: list[str] = []
    identity: dict[str, dict[str, str]] = {}
    for period_id in period_ids:
        for node_id in top_by_period[period_id]:
            if node_id not in identity:
                tracked.append(node_id)
                node = nodes_by_period[period_id][node_id]
                identity[node_id] = {"name": node["name"], "category": node["category"]}

    trajectories = []
    for node_id in tracked:
        points = []
        for period_id in period_ids:
            node = nodes_by_period[period_id].get(node_id)
            points.append(
                {
                    "period": period_id,
                    "rank": node["ranks"][metric] if node else None,
                    "value": node["metrics"][metric] if node else None,
                    "in_top": node_id in top_by_period[period_id],
                }
            )
        trajectories.append({"id": node_id, **identity[node_id], "points": points})

    changes = []
    for earlier, later in zip(period_ids, period_ids[1:]):
        earlier_top = set(top_by_period[earlier])
        later_top = set(top_by_period[later])
        movers = []
        for node_id in earlier_top & later_top:
            before = nodes_by_period[earlier][node_id]["ranks"][metric]
            after = nodes_by_period[later][node_id]["ranks"][metric]
            if before != after:
                movers.append(
                    {
                        "id": node_id,
                        **identity[node_id],
                        "from_rank": before,
                        "to_rank": after,
                    }
                )
        movers.sort(
            key=lambda item: (
                -abs(item["from_rank"] - item["to_rank"]),
                item["name"].casefold(),
            )
        )
        changes.append(
            {
                "from_period": earlier,
                "to_period": later,
                "entered": [
                    {"id": node_id, **identity[node_id]}
                    for node_id in top_by_period[later]
                    if node_id not in earlier_top
                ],
                "left": [
                    {"id": node_id, **identity[node_id]}
                    for node_id in top_by_period[earlier]
                    if node_id not in later_top
                ],
                "moved": movers,
            }
        )

    central_by_period = {}
    for period_id, network in networks_by_period.items():
        leaders = {}
        for ranking_metric in RANKING_METRICS:
            leader = next(
                (
                    node
                    for node in network["nodes"]
                    if node["ranks"][ranking_metric] == 1
                ),
                None,
            )
            leaders[ranking_metric] = (
                {
                    "id": leader["id"],
                    "name": leader["name"],
                    "category": leader["category"],
                    "value": leader["metrics"][ranking_metric],
                }
                if leader
                else None
            )
        central_by_period[period_id] = leaders

    return {
        "metric": metric,
        "top_k": top_k,
        "periods": period_ids,
        "trajectories": trajectories,
        "changes": changes,
        "central_by_period": central_by_period,
    }
