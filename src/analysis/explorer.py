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
de un nodo no depende de cuántos nodos se dibujen. Los pasos 1 a 4
(:func:`build_ranked_network`) no dependen de ``top_n`` ni de
``ranking_metric``; por eso su resultado se puede reutilizar y el paso 5
(:func:`select_shown_network`) es barato.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any, Literal, Sequence

import igraph as ig
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

# Períodos de análisis acordados para la evolución temporal, en orden cronológico.
# 2000–2020 agrupa la literatura de referencia anterior a las incubadoras.
PERIODS: tuple[dict[str, Any], ...] = (
    {"id": "2000-2020", "label": "2000–2020", "year_from": 2000, "year_to": 2020},
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
    # Entidades canónicas que se quitan antes de construir la red (por ejemplo, la
    # región que da contexto a todo el corpus); ordenadas para la clave de caché.
    excluded_entity_ids: tuple[str, ...] = ()

    def structural(self) -> "ExplorerFilters":
        """Los mismos filtros sin lo que solo afecta la selección final.

        Dos peticiones con el mismo valor estructural comparten red y métricas.
        """

        return replace(self, ranking_metric="pagerank", top_n=None)


@dataclass(frozen=True)
class RankedNetwork:
    """Red filtrada con sus métricas y rankings, antes de elegir ``top_n``."""

    graph: nx.Graph
    metrics: dict[str, dict[str, float]]
    ranking: dict[str, dict[str, int]]
    ordered: dict[str, tuple[str, ...]]
    stages: dict[str, Any]
    provenance: dict[str, Any]
    warnings: tuple[str, ...]
    excluded: tuple[dict[str, Any], ...] = ()


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


def _metric_igraph(graph: nx.Graph) -> tuple[list[str], ig.Graph, list[float]]:
    """Traduce la red a igraph con distancia inversa al peso.

    Un link fuerte acorta el camino. igraph implementa en C los caminos mínimos
    que dominan el costo de cercanía e intermediación.
    """

    nodes = list(graph)
    index = {node: position for position, node in enumerate(nodes)}
    edges: list[tuple[int, int]] = []
    distances: list[float] = []
    for source, target, attributes in graph.edges(data=True):
        edges.append((index[source], index[target]))
        distances.append(1.0 / float(attributes["analysis_weight"]))
    return nodes, ig.Graph(n=len(nodes), edges=edges, directed=False), distances


def _closeness(
    nodes: Sequence[str], metric_graph: ig.Graph, distances: Sequence[float]
) -> dict[str, float]:
    """Cercanía con la corrección de Wasserman y Faust para redes desconectadas.

    Coincide con ``networkx.closeness_centrality`` (``wf_improved=True``):
    igraph promedia solo sobre los nodos alcanzables y aquí se escala por la
    fracción de la red que cada nodo alcanza.
    """

    node_count = len(nodes)
    reachable = [0] * node_count
    for component in metric_graph.connected_components():
        for position in component:
            reachable[position] = len(component) - 1
    raw = metric_graph.closeness(weights=list(distances), normalized=True)

    closeness: dict[str, float] = {}
    for position, node in enumerate(nodes):
        value = raw[position]
        if node_count <= 1 or reachable[position] == 0 or value != value:
            closeness[node] = 0.0
        else:
            closeness[node] = value * reachable[position] / (node_count - 1)
    return closeness


def _betweenness(
    nodes: Sequence[str], metric_graph: ig.Graph, distances: Sequence[float]
) -> dict[str, float]:
    """Intermediación exacta, normalizada como ``networkx`` en redes no dirigidas."""

    node_count = len(nodes)
    if node_count <= 2:
        return {node: 0.0 for node in nodes}
    raw = metric_graph.betweenness(directed=False, weights=list(distances))
    scale = 2.0 / ((node_count - 1) * (node_count - 2))
    return {node: raw[position] * scale for position, node in enumerate(nodes)}


def compute_node_metrics(graph: nx.Graph) -> tuple[dict[str, dict[str, float]], dict]:
    """Calcula centralidades ponderadas y devuelve también su procedencia."""

    provenance = {"betweenness": "exact", "betweenness_sample_size": None}
    if graph.number_of_nodes() == 0:
        return {}, provenance

    pagerank = nx.pagerank(graph, weight="analysis_weight")
    nodes, metric_graph, distances = _metric_igraph(graph)
    closeness = _closeness(nodes, metric_graph, distances)
    betweenness = _betweenness(nodes, metric_graph, distances)

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


def exclude_entities(
    mentions: Sequence[MentionRecord],
    excluded_ids: Sequence[str],
) -> tuple[list[MentionRecord], tuple[dict[str, Any], ...]]:
    """Quita las menciones de las entidades excluidas y describe cada una.

    Una entidad pedida que no aparece en el alcance se informa con nombre nulo, para
    que la interfaz pueda mostrarla y permitir quitarla del filtro.
    """

    if not excluded_ids:
        return list(mentions), ()
    wanted = set(excluded_ids)
    kept: list[MentionRecord] = []
    found: dict[str, dict[str, Any]] = {}
    for mention in mentions:
        if mention.canonical_id in wanted:
            entity = found.setdefault(
                mention.canonical_id,
                {
                    "id": mention.canonical_id,
                    "name": mention.canonical_name,
                    "category": mention.category,
                    "mention_count": 0,
                },
            )
            entity["mention_count"] += 1
        else:
            kept.append(mention)
    described = tuple(
        found.get(
            entity_id,
            {"id": entity_id, "name": None, "category": None, "mention_count": 0},
        )
        for entity_id in sorted(wanted)
    )
    return kept, described


def _validate_ranking_metric(metric: str) -> None:
    if metric not in RANKING_METRICS:
        raise ExplorerFilterError(f"ranking_metric no soportada: {metric!r}")


def build_ranked_network(
    mentions: Sequence[MentionRecord],
    filters: ExplorerFilters,
) -> RankedNetwork:
    """Pasos 1 a 4: filtra la red y calcula métricas y rankings de cada nodo.

    El resultado no depende de ``top_n`` ni de ``ranking_metric`` y no se
    modifica después de construirlo, así que puede reutilizarse.
    """

    mentions, excluded = exclude_entities(mentions, filters.excluded_entity_ids)
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
    }

    def empty(warning: str) -> RankedNetwork:
        return RankedNetwork(
            graph=nx.Graph(),
            metrics={},
            ranking={metric: {} for metric in RANKING_METRICS},
            ordered={metric: () for metric in RANKING_METRICS},
            stages=stages,
            provenance={"betweenness": "exact", "betweenness_sample_size": None},
            warnings=(warning,),
            excluded=excluded,
        )

    if not any(mention.category in categories for mention in mentions):
        return empty("No hay menciones de las categorías seleccionadas en este alcance")

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
        return empty(
            "Ningún link supera los filtros de recurrencia y peso; "
            "pruebe bajar minimum_node_document_count o minimum_edge_weight"
        )

    metrics, provenance = compute_node_metrics(graph)
    ordered = {
        metric: tuple(rank_nodes(graph, metrics, metric)) for metric in RANKING_METRICS
    }
    ranking = {
        metric: {node: index for index, node in enumerate(nodes, start=1)}
        for metric, nodes in ordered.items()
    }
    return RankedNetwork(
        graph=graph,
        metrics=metrics,
        ranking=ranking,
        ordered=ordered,
        stages=stages,
        provenance=provenance,
        warnings=(),
        excluded=excluded,
    )


def select_shown_network(
    ranked: RankedNetwork,
    ranking_metric: str,
    top_n: int | None,
) -> dict[str, Any]:
    """Paso 5: elige los ``top_n`` nodos y arma una respuesta nueva.

    Copia todo lo que devuelve, de modo que quien la use puede modificarla sin
    alterar ``ranked``.
    """

    _validate_ranking_metric(ranking_metric)
    graph = ranked.graph
    stages = copy.deepcopy(ranked.stages)
    warnings = list(ranked.warnings)
    if graph.number_of_nodes() == 0:
        stages["shown"] = {"nodes": 0, "edges": 0}
        return {
            "nodes": [],
            "edges": [],
            "stages": stages,
            "metric_provenance": dict(ranked.provenance),
            "warnings": warnings,
            "excluded_entities": [dict(entity) for entity in ranked.excluded],
        }

    ordered = ranked.ordered[ranking_metric]
    shown_ids = ordered if top_n is None else ordered[:top_n]
    shown = graph.subgraph(shown_ids)

    nodes = [
        {
            "id": node,
            "name": graph.nodes[node]["canonical_name"],
            "category": graph.nodes[node]["category"],
            "mention_count": graph.nodes[node]["mention_count"],
            "sentence_count": graph.nodes[node]["sentence_count"],
            "metrics": dict(ranked.metrics[node]),
            "ranks": {
                metric: ranked.ranking[metric][node] for metric in RANKING_METRICS
            },
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
    if top_n is not None and len(ordered) > top_n:
        warnings.append(
            f"Se muestran los {top_n} nodos con mayor {ranking_metric} "
            f"de {len(ordered)} que superan los filtros"
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "stages": stages,
        "metric_provenance": dict(ranked.provenance),
        "warnings": warnings,
        "excluded_entities": [dict(entity) for entity in ranked.excluded],
    }


def build_explorer_network(
    mentions: Sequence[MentionRecord],
    filters: ExplorerFilters,
) -> dict[str, Any]:
    """Construye la red filtrada, sus métricas y el conteo de cada etapa."""

    _validate_ranking_metric(filters.ranking_metric)
    return select_shown_network(
        build_ranked_network(mentions, filters),
        filters.ranking_metric,
        filters.top_n,
    )


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
