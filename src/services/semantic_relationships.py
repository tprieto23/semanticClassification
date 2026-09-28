"""Construcción determinista de relaciones entre nodos semánticos."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from uuid import UUID

import networkx as nx
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, aliased

from src.analysis.graph_paths import graphml_path, semantic_network_filename
from src.analysis.leiden import graph_file_sha256
from src.config import settings
from src.models.canonical_entities import CanonicalEntity
from src.models.semantic_nodes import SemanticNode, SemanticNodeMember
from src.models.semantic_relationships import (
    SemanticNetworkSourceEdge,
    SemanticNodeRelationship,
)
from src.services.documents import DocumentoError
from src.services.semantic_nodes import (
    SemanticNodeError,
    _artifacts,
    _read_partition,
)
from src.services.network import _atomic_write_files

FORMULA_VERSION = "meta-network-relationship-v1"


class SemanticRelationshipError(DocumentoError):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message, status_code)


def _scope(incubator_number: int | None) -> tuple[str, int | None]:
    return ("incubators", incubator_number) if incubator_number else ("corpus", None)


def _safe_graph_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _ordered_pair(left: UUID, right: UUID) -> tuple[UUID, UUID]:
    return (left, right) if str(left) < str(right) else (right, left)


def _relationship_dict(row: SemanticNodeRelationship) -> dict:
    return {
        "id": row.id,
        "source_node_id": row.source_node_id,
        "target_node_id": row.target_node_id,
        "source_community_id": row.source_node.community_id,
        "target_community_id": row.target_node.community_id,
        "source_title": row.source_node.title,
        "target_title": row.target_node.title,
        "source_edge_count": row.source_edge_count,
        "weight": row.weight,
        "mean_source_weight": row.mean_source_weight,
        "sentence_support_sum": row.sentence_support_sum,
        "document_support_sum": row.document_support_sum,
        "formula_version": row.formula_version,
        "minimum_source_edge_weight": row.minimum_source_edge_weight,
        "status": row.status,
    }


class SemanticRelationshipService:
    @staticmethod
    def build(
        db: Session,
        *,
        projection_id: str,
        artifact_source: str,
        clustering_sha256: str,
        incubator_number: int | None,
        language: str,
        minimum_source_edge_weight: float,
        require_accepted_nodes: bool,
        force_recompute: bool,
    ) -> dict:
        if projection_id != "prac-infra-rul-v2":
            raise SemanticRelationshipError("Proyección no soportada", 404)
        scope_type, scope_id = _scope(incubator_number)
        try:
            graph_path, metadata_path = _artifacts(
                projection_id, scope_type, scope_id, language, artifact_source
            )
            graph, metadata = _read_partition(
                graph_path, metadata_path, clustering_sha256
            )
        except SemanticNodeError as exc:
            raise SemanticRelationshipError(exc.mensaje, exc.codigo_http) from exc

        metadata_projection = metadata.get("projection_id", projection_id)
        compatible_legacy = (
            artifact_source == "accepted-2026-08-25"
            and metadata_projection == "prac-infra-gov-v1"
            and projection_id == "prac-infra-rul-v2"
        )
        if metadata_projection != projection_id and not compatible_legacy:
            raise SemanticRelationshipError("La proyección del clustering no coincide")
        source_graph_sha256 = str(metadata["source"]["graphml_sha256"])
        node_statement = select(SemanticNode).where(
            SemanticNode.projection_id == projection_id,
            SemanticNode.artifact_source == artifact_source,
            SemanticNode.clustering_sha256 == clustering_sha256,
            SemanticNode.scope_type == scope_type,
            SemanticNode.language == language,
            SemanticNode.scope_id == (str(scope_id) if scope_id is not None else None),
        )
        nodes = list(db.scalars(node_statement).unique().all())
        if not nodes:
            raise SemanticRelationshipError(
                "No hay nodos semánticos registrados para esta partición", 404
            )
        if require_accepted_nodes:
            pending = [node.community_id for node in nodes if node.status != "accepted"]
            if pending:
                raise SemanticRelationshipError(
                    "Todos los nodos de la partición deben estar accepted antes de construir la meta-red"
                )

        existing = list(db.scalars(
            select(SemanticNodeRelationship).where(
                SemanticNodeRelationship.clustering_sha256 == clustering_sha256,
                SemanticNodeRelationship.formula_version == FORMULA_VERSION,
                SemanticNodeRelationship.minimum_source_edge_weight == minimum_source_edge_weight,
            )
        ).unique().all())
        if existing and not force_recompute:
            return SemanticRelationshipService._response(
                existing, projection_id, artifact_source, clustering_sha256,
                source_graph_sha256, minimum_source_edge_weight, cached=True,
            )
        if force_recompute:
            db.query(SemanticNodeRelationship).filter(
                SemanticNodeRelationship.clustering_sha256 == clustering_sha256,
                SemanticNodeRelationship.formula_version == FORMULA_VERSION,
                SemanticNodeRelationship.minimum_source_edge_weight == minimum_source_edge_weight,
            ).delete(synchronize_session=False)

        member_to_node: dict[str, UUID] = {}
        for node in nodes:
            for member in node.members:
                member_to_node[str(member.canonical_id)] = node.id

        missing_members = [
            str(canonical_id)
            for canonical_id, attrs in graph.nodes(data=True)
            if str(canonical_id) not in member_to_node
            and attrs.get("community_id") in {node.community_id for node in nodes}
        ]
        if missing_members:
            raise SemanticRelationshipError(
                "La membresía persistida no cubre todos los nodos de la partición"
            )

        try:
            graph_canonical_ids = [UUID(str(node)) for node in graph.nodes]
        except (TypeError, ValueError) as exc:
            raise SemanticRelationshipError(
                "El GraphML contiene un identificador de entidad que no es UUID"
            ) from exc
        known_canonicals = set(db.scalars(
            select(CanonicalEntity.id).where(
                CanonicalEntity.id.in_(graph_canonical_ids)
            )
        ).all())
        source_edges = list(db.scalars(select(SemanticNetworkSourceEdge).where(
            SemanticNetworkSourceEdge.clustering_sha256 == clustering_sha256
        )).all())
        if any(edge.source_graph_sha256 != source_graph_sha256 for edge in source_edges):
            raise SemanticRelationshipError(
                "La instantánea de aristas existente pertenece a otro grafo fuente"
            )
        new_source_edges: list[SemanticNetworkSourceEdge] = []
        source_keys = {
            (str(edge.source_canonical_id), str(edge.target_canonical_id))
            for edge in source_edges
        }
        for left, right, attrs in graph.edges(data=True):
            left_id, right_id = UUID(str(left)), UUID(str(right))
            source_id, target_id = _ordered_pair(left_id, right_id)
            key = (str(source_id), str(target_id))
            if key in source_keys:
                continue
            if left_id not in known_canonicals or right_id not in known_canonicals:
                raise SemanticRelationshipError(
                    "El GraphML contiene una entidad que no existe en canonical_entities"
                )
            try:
                weight = float(attrs.get("weight"))
            except (TypeError, ValueError) as exc:
                raise SemanticRelationshipError("Una arista fuente no tiene weight numérico") from exc
            if not isfinite(weight) or not weight > 0:
                raise SemanticRelationshipError("Cada weight fuente debe ser finito y positivo")
            supports: dict[str, int | None] = {}
            for support_name in ("sentence_count", "document_count"):
                raw_support = attrs.get(support_name)
                if raw_support is None:
                    supports[support_name] = None
                    continue
                try:
                    numeric_support = float(raw_support)
                except (TypeError, ValueError) as exc:
                    raise SemanticRelationshipError(
                        f"{support_name} debe ser numérico o nulo"
                    ) from exc
                if not isfinite(numeric_support) or numeric_support < 0 or not numeric_support.is_integer():
                    raise SemanticRelationshipError(
                        f"{support_name} debe ser un entero finito no negativo"
                    )
                supports[support_name] = int(numeric_support)
            new_source_edges.append(SemanticNetworkSourceEdge(
                clustering_sha256=clustering_sha256,
                source_graph_sha256=source_graph_sha256,
                source_canonical_id=source_id,
                target_canonical_id=target_id,
                source_category=str(graph.nodes[left].get("category") or "") or None,
                target_category=str(graph.nodes[right].get("category") or "") or None,
                weight=weight,
                sentence_count=supports["sentence_count"],
                document_count=supports["document_count"],
                attributes={str(key): _safe_graph_value(value) for key, value in attrs.items()},
            ))
            source_keys.add(key)
        if new_source_edges:
            db.add_all(new_source_edges)
            db.flush()

        missing_sentence_support = sum(
            edge.sentence_count is None for edge in source_edges
        )
        missing_document_support = sum(
            edge.document_count is None for edge in source_edges
        )

        member_a = aliased(SemanticNodeMember)
        member_b = aliased(SemanticNodeMember)
        node_a = aliased(SemanticNode)
        node_b = aliased(SemanticNode)
        source_node_id = case(
            (node_a.id < node_b.id, node_a.id), else_=node_b.id
        ).label("source_node_id")
        target_node_id = case(
            (node_a.id < node_b.id, node_b.id), else_=node_a.id
        ).label("target_node_id")
        aggregate = (
            select(
                source_node_id,
                target_node_id,
                func.count(SemanticNetworkSourceEdge.id).label("source_edge_count"),
                func.sum(SemanticNetworkSourceEdge.weight).label("weight"),
                func.avg(SemanticNetworkSourceEdge.weight).label("mean_source_weight"),
                func.coalesce(func.sum(SemanticNetworkSourceEdge.sentence_count), 0).label("sentence_support_sum"),
                func.coalesce(func.sum(SemanticNetworkSourceEdge.document_count), 0).label("document_support_sum"),
            )
            .join(member_a, member_a.canonical_id == SemanticNetworkSourceEdge.source_canonical_id)
            .join(member_b, member_b.canonical_id == SemanticNetworkSourceEdge.target_canonical_id)
            .join(node_a, and_(node_a.id == member_a.semantic_node_id, node_a.clustering_sha256 == clustering_sha256))
            .join(node_b, and_(node_b.id == member_b.semantic_node_id, node_b.clustering_sha256 == clustering_sha256))
            .where(
                SemanticNetworkSourceEdge.clustering_sha256 == clustering_sha256,
                SemanticNetworkSourceEdge.weight >= minimum_source_edge_weight,
                node_a.id != node_b.id,
            )
            .group_by(source_node_id, target_node_id)
        )
        aggregate_rows = db.execute(aggregate).all()
        node_by_id = {node.id: node for node in nodes}
        relationships: list[SemanticNodeRelationship] = []
        for row in aggregate_rows:
            source_node = node_by_id.get(row.source_node_id)
            target_node = node_by_id.get(row.target_node_id)
            if source_node is None or target_node is None:
                continue
            relationships.append(SemanticNodeRelationship(
                clustering_sha256=clustering_sha256,
                source_graph_sha256=source_graph_sha256,
                source_node_id=row.source_node_id,
                target_node_id=row.target_node_id,
                formula_version=FORMULA_VERSION,
                minimum_source_edge_weight=minimum_source_edge_weight,
                source_edge_count=int(row.source_edge_count),
                weight=round(float(row.weight), 12),
                mean_source_weight=round(float(row.mean_source_weight), 12),
                sentence_support_sum=int(row.sentence_support_sum),
                document_support_sum=int(row.document_support_sum),
                parameters={
                    "formula_version": FORMULA_VERSION,
                    "minimum_source_edge_weight": minimum_source_edge_weight,
                    "source_weight_attribute": "weight",
                    "directed": False,
                    "missing_sentence_support_edges": missing_sentence_support,
                    "missing_document_support_edges": missing_document_support,
                },
                status="calculated",
            ))
        db.add_all(relationships)
        db.commit()
        for relationship in relationships:
            db.refresh(relationship)
        return SemanticRelationshipService._response(
            relationships, projection_id, artifact_source, clustering_sha256,
            source_graph_sha256, minimum_source_edge_weight, cached=False,
        )

    @staticmethod
    def _response(
        relationships: list[SemanticNodeRelationship], projection_id: str,
        artifact_source: str, clustering_sha256: str, source_graph_sha256: str,
        minimum_source_edge_weight: float, cached: bool,
    ) -> dict:
        return {
            "generated_at": datetime.now(timezone.utc),
            "projection_id": projection_id,
            "artifact_source": artifact_source,
            "clustering_sha256": clustering_sha256,
            "source_graph_sha256": source_graph_sha256,
            "formula_version": FORMULA_VERSION,
            "parameters": {
                "minimum_source_edge_weight": minimum_source_edge_weight,
                "source_weight_attribute": "weight",
                "directed": False,
                "missing_sentence_support_edges": (
                    relationships[0].parameters.get("missing_sentence_support_edges", 0)
                    if relationships else 0
                ),
                "missing_document_support_edges": (
                    relationships[0].parameters.get("missing_document_support_edges", 0)
                    if relationships else 0
                ),
            },
            "counts": {
                "semantic_nodes": len({item.source_node_id for item in relationships} | {item.target_node_id for item in relationships}),
                "relationships": len(relationships),
                "source_edges": sum(item.source_edge_count for item in relationships),
            },
            "cached": cached,
            "relationships": [_relationship_dict(item) for item in relationships],
        }

    @staticmethod
    def list(
        db: Session, *, clustering_sha256: str, minimum_source_edge_weight: float = 0.0
    ) -> list[dict]:
        rows = list(db.scalars(select(SemanticNodeRelationship).where(
            SemanticNodeRelationship.clustering_sha256 == clustering_sha256,
            SemanticNodeRelationship.minimum_source_edge_weight == minimum_source_edge_weight,
        )).unique().all())
        return [_relationship_dict(row) for row in rows]

    @staticmethod
    def export_graphml(
        db: Session,
        *,
        clustering_sha256: str,
        minimum_source_edge_weight: float = 0.0,
        include_isolates: bool = True,
    ) -> dict:
        nodes = list(db.scalars(
            select(SemanticNode).where(
                SemanticNode.clustering_sha256 == clustering_sha256
            )
        ).unique().all())
        if not nodes:
            raise SemanticRelationshipError(
                "No hay nodos semánticos registrados para esta partición", 404
            )

        partition = {
            (
                node.projection_id,
                node.artifact_source,
                node.scope_type,
                node.scope_id,
                node.language,
                node.source_graph_sha256,
            )
            for node in nodes
        }
        if len(partition) != 1:
            raise SemanticRelationshipError(
                "Los nodos de la partición no comparten la misma procedencia"
            )
        (
            projection_id,
            artifact_source,
            scope_type,
            scope_id,
            language,
            source_graph_sha256,
        ) = partition.pop()

        relationships = list(db.scalars(
            select(SemanticNodeRelationship).where(
                SemanticNodeRelationship.clustering_sha256 == clustering_sha256,
                SemanticNodeRelationship.formula_version == FORMULA_VERSION,
                SemanticNodeRelationship.minimum_source_edge_weight
                == minimum_source_edge_weight,
            )
        ).unique().all())
        connected_ids = {
            node_id
            for relationship in relationships
            for node_id in (relationship.source_node_id, relationship.target_node_id)
        }
        exported_nodes = nodes if include_isolates else [
            node for node in nodes if node.id in connected_ids
        ]
        exported_ids = {node.id for node in exported_nodes}

        graph = nx.Graph()
        graph.graph.update({
            "network_type": "semantic-meta-network",
            "projection_id": projection_id,
            "artifact_source": artifact_source,
            "clustering_sha256": clustering_sha256,
            "source_graph_sha256": source_graph_sha256,
            "formula_version": FORMULA_VERSION,
            "minimum_source_edge_weight": minimum_source_edge_weight,
            "include_isolates": include_isolates,
            "language": language,
            "scope_type": scope_type,
            "scope_id": scope_id or "",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
        for node in exported_nodes:
            category_counts = {category: 0 for category in ("PRAC", "INFRA", "RUL")}
            for member in node.members:
                if member.category in category_counts:
                    category_counts[member.category] += 1
            graph.add_node(
                str(node.id),
                label=node.title or node.community_id,
                title=node.title or "",
                description=node.description or "",
                community_id=node.community_id,
                status=node.status,
                projection_id=node.projection_id,
                artifact_source=node.artifact_source,
                language=node.language,
                document_count=node.document_count,
                member_count=len(node.members),
                prac_count=category_counts["PRAC"],
                infra_count=category_counts["INFRA"],
                rul_count=category_counts["RUL"],
            )
        for relationship in relationships:
            if (
                relationship.source_node_id not in exported_ids
                or relationship.target_node_id not in exported_ids
            ):
                continue
            graph.add_edge(
                str(relationship.source_node_id),
                str(relationship.target_node_id),
                relationship_id=str(relationship.id),
                weight=relationship.weight,
                source_edge_count=relationship.source_edge_count,
                mean_source_weight=relationship.mean_source_weight,
                sentence_support_sum=relationship.sentence_support_sum,
                document_support_sum=relationship.document_support_sum,
                formula_version=relationship.formula_version,
                minimum_source_edge_weight=relationship.minimum_source_edge_weight,
                status=relationship.status,
            )

        target = graphml_path(
            scope_type,
            scope_id,
            language,
            semantic_network_filename(projection_id),
        )
        _atomic_write_files(
            {target: lambda temporary: nx.write_graphml(graph, temporary)},
            target.parent,
        )
        relative_path = target.relative_to(settings.STORAGE_GRAPHS).as_posix()
        return {
            "generated_at": datetime.now(timezone.utc),
            "clustering_sha256": clustering_sha256,
            "formula_version": FORMULA_VERSION,
            "minimum_source_edge_weight": minimum_source_edge_weight,
            "include_isolates": include_isolates,
            "counts": {
                "nodes": graph.number_of_nodes(),
                "relationships": graph.number_of_edges(),
                "isolates": nx.number_of_isolates(graph),
            },
            "graphml_path": relative_path,
            "graphml_url": "",
            "graphml_sha256": graph_file_sha256(target),
        }
