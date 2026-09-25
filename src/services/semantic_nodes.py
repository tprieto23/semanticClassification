"""Promoción y descripción editorial de comunidades Leiden aceptadas."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import networkx as nx
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.analysis.graph_paths import graphml_path, json_path, leiden_filename
from src.analysis.leiden import graph_file_sha256
from src.config import settings
from src.models.canonical_entities import CanonicalEntity
from src.models.documents import Document
from src.models.entities import Entity
from src.models.semantic_nodes import SemanticNode, SemanticNodeMember
from src.models.sentences import Sentence
from src.services.documents import DocumentoError
from src.services.llm_client import get_anthropic_client
from src.services.network import _lock_for

logger = logging.getLogger(__name__)

PROMPT_VERSION = "semantic-node-v1"
SEMANTIC_NODE_TOOL_NAME = "submit_semantic_node_description"
SEMANTIC_NODE_TOOL = {
    "name": SEMANTIC_NODE_TOOL_NAME,
    "description": "Entrega el título, la descripción y su evidencia auditable.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "description": {"type": "string", "minLength": 1, "maxLength": 5000},
            "supporting_evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "claim": {"type": "string", "minLength": 1},
                        "canonical_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "sentence_refs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "document_id": {"type": "string"},
                                    "sentence_id": {"type": "string"},
                                },
                                "required": ["document_id", "sentence_id"],
                            },
                        },
                    },
                    "required": ["claim", "canonical_ids", "sentence_refs"],
                },
            },
            "uncertainties": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["title", "description", "supporting_evidence", "uncertainties"],
    },
}
VALID_CATEGORIES = {"PRAC", "INFRA", "GOV"}
LEGACY_ACCEPTED_DIR = Path(
    "corpus/language-es/projections/prac-infra-gov-v1/"
    "constructions/document-recurrent-core-v1/node-documents-2/"
    "edge-weight-fractional-document/with-minor-components/"
    "views/main-component/all/clusterings/leiden-v1/"
    "objective-modularity/resolution-1/seed-42/iterations-converge/weight-weight"
)


class SemanticNodeError(DocumentoError):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message, status_code)


def _scope(incubator_number: int | None, language: str) -> tuple[str, int | None]:
    return ("incubators", incubator_number) if incubator_number else ("corpus", None)


def _artifacts(
    projection_id: str,
    scope_type: str,
    scope_id: int | None,
    language: str,
    artifact_source: str,
) -> tuple[Path, Path]:
    if artifact_source == "accepted-2026-08-25":
        if (projection_id, scope_type, scope_id, language) != (
            "prac-infra-gov-v1", "corpus", None, "es"
        ):
            raise SemanticNodeError(
                "La partición histórica aceptada solo corresponde al corpus español"
            )
        root = settings.STORAGE_NETWORK / LEGACY_ACCEPTED_DIR
        return root / "network_clustered.graphml", root / "clustering_summary.json"
    if artifact_source != "official":
        raise SemanticNodeError("Fuente Leiden no soportada")
    name = leiden_filename(f"backbone_{projection_id}", {})
    return (
        graphml_path(scope_type, scope_id, language, name),
        json_path(scope_type, scope_id, language, name),
    )


def _read_partition(graph_path: Path, metadata_path: Path, expected_hash: str):
    with _lock_for(graph_path.parent):
        if not graph_path.is_file() or not metadata_path.is_file():
            raise SemanticNodeError("No existe un clustering Leiden para este alcance", 404)
        current_hash = graph_file_sha256(graph_path)
        if current_hash != expected_hash:
            raise SemanticNodeError(
                "La partición Leiden fue reemplazada; consulta la huella del artefacto actual"
            )
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            graph = nx.read_graphml(graph_path)
        except (OSError, ValueError, nx.NetworkXError) as exc:
            raise SemanticNodeError("Artefactos Leiden ilegibles") from exc
    if metadata.get("status") != "completed":
        raise SemanticNodeError("La partición Leiden no está completa")
    if graph.is_directed() or graph.is_multigraph():
        raise SemanticNodeError("El grafo Leiden debe ser simple y no dirigido")
    if metadata.get("source", {}).get("graphml_sha256") != graph.graph.get(
        "source_graph_sha256"
    ):
        raise SemanticNodeError("Los metadatos y el GraphML Leiden no coinciden")
    return graph, metadata


def _support(
    db: Session, member_ids: list[UUID], scope_type: str,
    scope_id: int | None, language: str,
) -> tuple[list[dict], int]:
    statement = (
        select(Document.id, Document.incubator_number, Entity.canonical_id)
        .join(Entity, Entity.document_id == Document.id)
        .where(Document.status == "fuzzyMatching", Entity.canonical_id.in_(member_ids))
        .distinct()
    )
    if scope_type == "incubators":
        statement = statement.where(Document.incubator_number == scope_id)
    if language != "all":
        statement = statement.where(Document.language == language)

    by_incubator: dict[int | None, dict[str, set]] = defaultdict(
        lambda: {"documents": set(), "members": set()}
    )
    all_documents: set[UUID] = set()
    for document_id, incubator, canonical_id in db.execute(statement):
        by_incubator[incubator]["documents"].add(document_id)
        by_incubator[incubator]["members"].add(canonical_id)
        all_documents.add(document_id)
    rows = [
        {
            "incubator_number": incubator,
            "document_count": len(values["documents"]),
            "member_count": len(values["members"]),
            "document_ids": sorted(str(item) for item in values["documents"]),
        }
        for incubator, values in sorted(
            by_incubator.items(), key=lambda item: (item[0] is None, item[0] or 0)
        )
    ]
    return rows, len(all_documents)


def _read_node(db: Session, node_id: UUID) -> SemanticNode:
    node = db.get(SemanticNode, node_id)
    if node is None:
        raise SemanticNodeError(f"Nodo semántico {node_id} no encontrado", 404)
    return node


def _node_dict(node: SemanticNode) -> dict:
    return {
        "id": node.id,
        "projection_id": node.projection_id,
        "artifact_source": node.artifact_source,
        "community_id": node.community_id,
        "clustering_sha256": node.clustering_sha256,
        "source_graph_sha256": node.source_graph_sha256,
        "scope_type": node.scope_type,
        "scope_id": node.scope_id,
        "language": node.language,
        "provenance": node.provenance,
        "incubator_support": node.incubator_support,
        "document_count": node.document_count,
        "status": node.status,
        "title": node.title,
        "description": node.description,
        "generation": node.generation,
        "members": [
            {
                "canonical_id": item.canonical_id,
                "canonical_name": item.canonical_name,
                "category": item.category,
            }
            for item in sorted(node.members, key=lambda m: (m.category, m.canonical_name))
        ],
        "created_at": node.created_at,
        "updated_at": node.updated_at,
    }


def _evidence(db: Session, node: SemanticNode, graph: nx.Graph) -> dict:
    member_ids = {str(member.canonical_id) for member in node.members}
    internal_edges = [
        (str(source), str(target), attributes)
        for source, target, attributes in graph.edges(data=True)
        if str(source) in member_ids and str(target) in member_ids
    ]
    internal_edges.sort(
        key=lambda edge: (-float(edge[2].get("weight", 1)), edge[0], edge[1])
    )
    selected_edges = []
    by_category_pair: dict[str, int] = defaultdict(int)
    for edge in internal_edges:
        pair = str(edge[2].get("category_pair", "unknown"))
        if by_category_pair[pair] < 3:
            selected_edges.append(edge)
            by_category_pair[pair] += 1
    selected_edges = selected_edges[:18]
    selected_keys = {(source, target) for source, target, _ in selected_edges}
    for edge in internal_edges:
        if len(selected_edges) >= 18:
            break
        if (edge[0], edge[1]) not in selected_keys:
            selected_edges.append(edge)
    sentences: dict[tuple[str, str], dict] = {}
    for source, target, attributes in selected_edges:
        left, right = Entity.__table__.alias("left_mention"), Entity.__table__.alias(
            "right_mention"
        )
        statement = (
            select(Sentence.document_id, Sentence.sentence_id, Sentence.text)
            .join(left, and_(
                left.c.document_id == Sentence.document_id,
                left.c.sentence_id == Sentence.sentence_id,
            ))
            .join(right, and_(
                right.c.document_id == Sentence.document_id,
                right.c.sentence_id == Sentence.sentence_id,
            ))
            .join(Document, Document.id == Sentence.document_id)
            .where(left.c.canonical_id == UUID(source), right.c.canonical_id == UUID(target))
            .where(Document.status == "fuzzyMatching")
            .distinct()
            .order_by(Sentence.document_id, Sentence.sentence_id)
            .limit(2)
        )
        if node.scope_type == "incubators":
            statement = statement.where(Document.incubator_number == int(node.scope_id))
        if node.language != "all":
            statement = statement.where(Document.language == node.language)
        for document_id, sentence_id, sentence_text in db.execute(statement):
            key = (str(document_id), sentence_id)
            item = sentences.setdefault(key, {
                "document_id": str(document_id),
                "sentence_id": sentence_id,
                "text": sentence_text[:2000],
                "truncated": len(sentence_text) > 2000,
                "canonical_ids": set(),
            })
            item["canonical_ids"].update((source, target))

    return {
        "community_id": node.community_id,
        "provenance": node.provenance,
        "members": [
            {
                "canonical_id": str(member.canonical_id),
                "canonical_name": member.canonical_name,
                "category": member.category,
            }
            for member in sorted(node.members, key=lambda m: (m.category, m.canonical_name))
        ],
        "internal_edges": [
            {
                "source_canonical_id": source,
                "target_canonical_id": target,
                "sentence_count": attributes.get("sentence_count"),
                "document_count": attributes.get("document_count"),
                "analysis_weight": attributes.get("weight"),
            }
            for source, target, attributes in selected_edges
        ],
        "evidence_sentences": [
            {**item, "canonical_ids": sorted(item["canonical_ids"])}
            for item in sentences.values()
        ],
        "incubator_support": node.incubator_support,
        "evidence_coverage": {
            "internal_edge_count": len(internal_edges),
            "selected_edge_count": len(selected_edges),
            "selected_sentence_count": len(sentences),
            "selection": "hasta 3 aristas por par de categorías y 18 en total; hasta 2 oraciones por arista",
        },
    }


class SemanticNodeService:
    @staticmethod
    def leiden_source(
        *, projection_id: str, artifact_source: str,
        incubator_number: int | None, language: str
    ) -> dict:
        if projection_id != "prac-infra-gov-v1":
            raise SemanticNodeError("Proyección no soportada", 404)
        scope_type, scope_id = _scope(incubator_number, language)
        graph_path, metadata_path = _artifacts(
            projection_id, scope_type, scope_id, language, artifact_source
        )
        if not graph_path.is_file():
            raise SemanticNodeError("No existe un clustering Leiden para este alcance", 404)
        current_hash = graph_file_sha256(graph_path)
        graph, metadata = _read_partition(graph_path, metadata_path, current_hash)
        sizes: dict[str, int] = defaultdict(int)
        for _, attributes in graph.nodes(data=True):
            sizes[str(attributes["community_id"])] += 1
        return {
            "projection_id": projection_id,
            "artifact_source": artifact_source,
            "incubator_number": incubator_number if incubator_number is not None else "all",
            "language": language,
            "clustering_sha256": current_hash,
            "source_graph_sha256": metadata["source"]["graphml_sha256"],
            "generated_at": metadata.get("generated_at"),
            "configuration": metadata.get("configuration", {}),
            "communities": [
                {"community_id": key, "member_count": count}
                for key, count in sorted(sizes.items())
            ],
        }

    @staticmethod
    def promote(
        db: Session, *, projection_id: str, artifact_source: str, community_id: str,
        incubator_number: int | None, language: str, expected_hash: str,
    ) -> dict:
        if projection_id != "prac-infra-gov-v1":
            raise SemanticNodeError("Proyección no soportada", 404)
        scope_type, scope_id = _scope(incubator_number, language)
        graph_path, metadata_path = _artifacts(
            projection_id, scope_type, scope_id, language, artifact_source
        )
        graph, metadata = _read_partition(graph_path, metadata_path, expected_hash)
        if artifact_source == "official" and metadata.get("projection_id") != projection_id:
            raise SemanticNodeError("La proyección de Leiden no coincide")
        if artifact_source == "official":
            scope_details = metadata.get("scope_details", {})
            if (
                scope_details.get("type") != scope_type
                or str(scope_details.get("id") or "") != str(scope_id or "")
                or scope_details.get("language") != language
            ):
                raise SemanticNodeError("El alcance de Leiden no coincide")

        members = [
            (str(canonical_id), attributes)
            for canonical_id, attributes in graph.nodes(data=True)
            if attributes.get("community_id") == community_id
        ]
        if not members:
            raise SemanticNodeError(f"Comunidad {community_id} no encontrada", 404)
        member_rows = []
        for canonical_id, attributes in members:
            try:
                parsed_id = UUID(canonical_id)
            except ValueError as exc:
                raise SemanticNodeError("El GraphML contiene un canonical_id inválido") from exc
            category = str(attributes.get("category", ""))
            if category not in VALID_CATEGORIES:
                raise SemanticNodeError("El cluster contiene una categoría no proyectada")
            name = str(
                attributes.get("canonical_name") or attributes.get("label") or canonical_id
            )
            member_rows.append((parsed_id, name, category))

        existing = db.scalar(
            select(SemanticNode).where(
                SemanticNode.clustering_sha256 == expected_hash,
                SemanticNode.community_id == community_id,
            )
        )
        if existing is not None:
            return _node_dict(existing)

        actual_ids = set(
            db.scalars(
                select(CanonicalEntity.id).where(
                    CanonicalEntity.id.in_([item[0] for item in member_rows])
                )
            ).all()
        )
        if actual_ids != {item[0] for item in member_rows}:
            raise SemanticNodeError(
                "Faltan entidades canónicas de esta partición en la base de datos"
            )

        support, document_count = _support(
            db, [item[0] for item in member_rows], scope_type, scope_id, language
        )
        node = SemanticNode(
            projection_id=projection_id,
            artifact_source=artifact_source,
            community_id=community_id,
            clustering_sha256=expected_hash,
            source_graph_sha256=str(metadata["source"]["graphml_sha256"]),
            scope_type=scope_type,
            scope_id=str(scope_id) if scope_id is not None else None,
            language=language,
            provenance={
                "graphml": str(
                    graph_path.relative_to(
                        settings.STORAGE_NETWORK
                        if artifact_source != "official"
                        else settings.STORAGE_GRAPHS
                    )
                ),
                "artifact_source": artifact_source,
                "source_graph_sha256": metadata["source"]["graphml_sha256"],
                "configuration": metadata.get("configuration", {}),
                "filters": metadata.get("filters", {}),
                "generated_at": metadata.get("generated_at"),
                "support_calculated_at": datetime.now(timezone.utc).isoformat(),
            },
            incubator_support=support,
            document_count=document_count,
            members=[
                SemanticNodeMember(
                    canonical_id=canonical_id, canonical_name=name, category=category
                )
                for canonical_id, name, category in member_rows
            ],
        )
        try:
            db.add(node)
            db.commit()
            db.refresh(node)
        except Exception:
            db.rollback()
            raise
        return _node_dict(node)

    @staticmethod
    def get(db: Session, node_id: UUID) -> dict:
        return _node_dict(_read_node(db, node_id))

    @staticmethod
    def list(
        db: Session, *, skip: int, limit: int, status: str | None,
        incubator_number: int | None,
    ) -> dict:
        statement = select(SemanticNode)
        if status is not None:
            statement = statement.where(SemanticNode.status == status)
        if incubator_number is not None:
            statement = statement.where(
                SemanticNode.incubator_support.contains(
                    [{"incubator_number": incubator_number}]
                )
            )
        total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        nodes = db.scalars(
            statement.order_by(SemanticNode.created_at.desc(), SemanticNode.id)
            .offset(skip).limit(limit)
        ).all()
        return {"items": [_node_dict(node) for node in nodes], "total": total,
                "skip": skip, "limit": limit}

    @staticmethod
    def edit(db: Session, node_id: UUID, changes: dict) -> dict:
        node = _read_node(db, node_id)
        for key, value in changes.items():
            if key in {"title", "description"}:
                setattr(node, key, value)
        if changes.get("status") is not None:
            if changes["status"] == "accepted" and (not node.title or not node.description):
                raise SemanticNodeError("Aceptar un nodo requiere título y descripción")
            node.status = changes["status"]
        elif "title" in changes or "description" in changes:
            node.status = "draft"
        if "title" in changes or "description" in changes:
            node.generation = {**(node.generation or {}), "manually_edited": True}
        node.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(node)
        return _node_dict(node)

    @staticmethod
    def generate(db: Session, node_id: UUID) -> dict:
        node = _read_node(db, node_id)
        if node.status == "accepted":
            raise SemanticNodeError(
                "El nodo aceptado debe volver a draft antes de regenerar su descripción"
            )
        if node.status == "retired":
            raise SemanticNodeError("No se genera una descripción para un nodo retirado")
        last_updated = node.updated_at
        graph_path, metadata_path = _artifacts(
            node.projection_id, node.scope_type,
            int(node.scope_id) if node.scope_id else None, node.language,
            node.artifact_source,
        )
        graph, _ = _read_partition(graph_path, metadata_path, node.clustering_sha256)
        current_support, current_document_count = _support(
            db, [member.canonical_id for member in node.members],
            node.scope_type, int(node.scope_id) if node.scope_id else None,
            node.language,
        )
        if (
            current_support != node.incubator_support
            or current_document_count != node.document_count
        ):
            raise SemanticNodeError(
                "El soporte documental cambió desde el registro del nodo; revisa la evidencia antes de generar"
            )
        evidence = _evidence(db, node, graph)
        prompt_path = Path(settings.SEMANTIC_NODE_PROMPT_PATH)
        prompt = prompt_path.read_text(encoding="utf-8")
        try:
            response = get_anthropic_client().messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2500,
                system=prompt,
                messages=[{"role": "user", "content": json.dumps(evidence, ensure_ascii=False)}],
                tools=[SEMANTIC_NODE_TOOL],
                tool_choice={"type": "tool", "name": SEMANTIC_NODE_TOOL_NAME},
            )
        except Exception as exc:
            logger.exception(
                "Falló la generación de descripción del nodo semántico %s con el modelo %s",
                node_id,
                settings.ANTHROPIC_MODEL,
            )
            raise SemanticNodeError("No fue posible generar la descripción", 502) from exc
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise SemanticNodeError("La respuesta del LLM fue truncada", 502)
        result = next(
            (
                block.input
                for block in response.content
                if getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == SEMANTIC_NODE_TOOL_NAME
            ),
            None,
        )
        if result is None:
            raw = "".join(
                block.text for block in response.content
                if getattr(block, "type", None) == "text"
            )
            try:
                result = json.loads(raw)
            except (TypeError, ValueError) as exc:
                raise SemanticNodeError("El LLM no devolvió JSON válido", 502) from exc
        if not isinstance(result, dict) or set(result) != {
            "title", "description", "supporting_evidence", "uncertainties"
        }:
            raise SemanticNodeError("La respuesta del LLM no cumple el contrato", 502)
        title, description = result["title"], result["description"]
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise SemanticNodeError("El LLM no produjo un título válido", 502)
        if not isinstance(description, str) or not description.strip() or len(description) > 5000:
            raise SemanticNodeError("El LLM no produjo una descripción válida", 502)
        if not isinstance(result["supporting_evidence"], list) or not isinstance(result["uncertainties"], list):
            raise SemanticNodeError("El LLM no produjo evidencia e incertidumbres válidas", 502)
        allowed_members = {str(member.canonical_id) for member in node.members}
        allowed_sentences = {
            (item["document_id"], item["sentence_id"])
            for item in evidence["evidence_sentences"]
        }
        members_by_sentence = {
            (item["document_id"], item["sentence_id"]): set(item["canonical_ids"])
            for item in evidence["evidence_sentences"]
        }
        for claim in result["supporting_evidence"]:
            if not isinstance(claim, dict) or not isinstance(claim.get("claim"), str):
                raise SemanticNodeError("Evidencia generada inválida", 502)
            if not isinstance(claim.get("canonical_ids"), list) or not set(claim["canonical_ids"]) <= allowed_members:
                raise SemanticNodeError("El LLM citó entidades ajenas al cluster", 502)
            refs = claim.get("sentence_refs")
            if not isinstance(refs, list) or any(
                not isinstance(ref, dict) or
                (ref.get("document_id"), ref.get("sentence_id")) not in allowed_sentences
                for ref in refs
            ):
                raise SemanticNodeError("El LLM citó oraciones ajenas a la evidencia", 502)
            if refs and not set(claim["canonical_ids"]) <= set().union(*(
                members_by_sentence[(ref["document_id"], ref["sentence_id"])]
                for ref in refs
            )):
                raise SemanticNodeError("Las entidades citadas no aparecen en las oraciones citadas", 502)
        if any(not isinstance(item, str) for item in result["uncertainties"]):
            raise SemanticNodeError("Incertidumbres generadas inválidas", 502)

        db.refresh(node)
        if node.updated_at != last_updated or node.status in {"accepted", "retired"}:
            raise SemanticNodeError(
                "El nodo cambió durante la generación; revisa su versión actual"
            )
        previous_generation = node.generation or {}
        history = list(previous_generation.get("previous_generations", []))
        if previous_generation:
            history.append({
                key: value for key, value in previous_generation.items()
                if key != "previous_generations"
            })
        node.title = title.strip()
        node.description = description.strip()
        node.status = "draft"
        node.generation = {
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "model": settings.ANTHROPIC_MODEL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "supporting_evidence": result["supporting_evidence"],
            "uncertainties": result["uncertainties"],
            "original_title": title,
            "original_description": description,
            "evidence_coverage": evidence["evidence_coverage"],
            "manually_edited": False,
            "previous_generations": history,
        }
        node.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(node)
        return _node_dict(node)
