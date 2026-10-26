"""Servicio de lectura para el explorador interactivo de entidades.

No escribe en PostgreSQL ni en ``s3/``: consulta documentos listos y sus
menciones canonicalizadas y delega la construcción de la red en
:mod:`src.analysis.explorer`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.analysis.cooccurrence import CATEGORY_RANK, load_db_mentions
from src.analysis.explorer import (
    CATEGORY_LABELS,
    EXPLORER_VERSION,
    PERIODS,
    PERIODS_BY_ID,
    ExplorerFilterError,
    ExplorerFilters,
    build_explorer_network,
    compare_rankings,
)
from src.categories import ACTIVE_CATEGORIES, CATEGORY_DEFINITIONS, LEGACY_CATEGORIES
from src.models.canonical_entities import CanonicalEntity
from src.models.documents import Document
from src.models.entities import Entity
from src.models.sentences import Sentence
from src.services.documents import DocumentoError

READY_STATUS = "fuzzyMatching"
# Solo el sector acordado entra en el análisis salvo que se pida explícitamente "all".
DEFAULT_PRODUCTIVE_SECTOR = "Agroforestry"


class ExplorerFiltroInvalido(DocumentoError):
    def __init__(self, detail: str):
        super().__init__(detail, 422)


class ExplorerEvidenciaNoEncontrada(DocumentoError):
    def __init__(self, source_id: str, target_id: str):
        super().__init__(
            f"No hay oraciones compartidas entre {source_id} y {target_id} "
            "en el alcance seleccionado",
            404,
        )


@dataclass(frozen=True)
class ExplorerScope:
    period: str | None = None
    incubator_number: int | None = None
    language: str | None = None
    document_ids: tuple[str, ...] | None = None
    productive_sector: str | None = DEFAULT_PRODUCTIVE_SECTOR

    def validate(self) -> None:
        if self.period is not None and self.period not in PERIODS_BY_ID:
            raise ExplorerFiltroInvalido(
                f"Período desconocido: {self.period!r}. Use 'all' o uno de: "
                + ", ".join(PERIODS_BY_ID)
            )


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _document_row(document: Any) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "name": document.original_filename,
        "year": document.year,
        "incubator_number": document.incubator_number,
        "language": document.language,
        "document_type": document.document_type,
    }


def _scoped_documents(db: Session, scope: ExplorerScope) -> list[Any]:
    statement = select(
        Document.id,
        Document.original_filename,
        Document.year,
        Document.incubator_number,
        Document.language,
        Document.document_type,
        Document.productive_sector,
    ).where(Document.status == READY_STATUS)
    if scope.productive_sector is not None:
        statement = statement.where(
            Document.productive_sector == scope.productive_sector
        )
    if scope.period is not None:
        period = PERIODS_BY_ID[scope.period]
        statement = statement.where(
            Document.year.between(period["year_from"], period["year_to"])
        )
    if scope.incubator_number is not None:
        statement = statement.where(Document.incubator_number == scope.incubator_number)
    if scope.language is not None:
        statement = statement.where(Document.language == scope.language)
    if scope.document_ids is not None:
        statement = statement.where(
            Document.id.in_([UUID(value) for value in scope.document_ids])
        )
    return list(
        db.execute(statement.order_by(Document.year, Document.original_filename)).all()
    )


def _scope_summary(scope: ExplorerScope, documents: Sequence[Any]) -> dict[str, Any]:
    return {
        "period": scope.period or "all",
        "incubator_number": scope.incubator_number or "all",
        "language": scope.language or "all",
        "document_ids": list(scope.document_ids) if scope.document_ids else None,
        "productive_sector": scope.productive_sector or "all",
        "document_count": len(documents),
        "documents_without_year": sum(
            1 for document in documents if document.year is None
        ),
    }


def _filters_summary(filters: ExplorerFilters) -> dict[str, Any]:
    return {
        "categories": list(filters.categories) if filters.categories else None,
        "link_mode": filters.link_mode,
        "category_pairs": (
            ["--".join(pair) for pair in filters.category_pairs]
            if filters.category_pairs
            else None
        ),
        "minimum_node_document_count": filters.minimum_node_document_count,
        "edge_weighting": filters.edge_weighting,
        "minimum_edge_weight": filters.minimum_edge_weight,
        "ranking_metric": filters.ranking_metric,
        "top_n": filters.top_n,
    }


class ExplorerService:
    @staticmethod
    def meta(
        db: Session, productive_sector: str | None = DEFAULT_PRODUCTIVE_SECTOR
    ) -> dict[str, Any]:
        scope = ExplorerScope(productive_sector=productive_sector)
        documents = _scoped_documents(db, scope)
        all_ready = _scoped_documents(db, ExplorerScope(productive_sector=None))
        category_statement = (
            select(Entity.category, func.count(func.distinct(Entity.canonical_id)))
            .join(Document, Document.id == Entity.document_id)
            .where(Document.status == READY_STATUS)
            .group_by(Entity.category)
        )
        if productive_sector is not None:
            category_statement = category_statement.where(
                Document.productive_sector == productive_sector
            )
        category_counts = dict(db.execute(category_statement).all())
        categories = [
            {
                "code": code,
                "label": CATEGORY_LABELS.get(code, code),
                "definition": CATEGORY_DEFINITIONS.get(code),
                "legacy": code in LEGACY_CATEGORIES,
                "entity_count": int(category_counts.get(code, 0)),
            }
            for code in sorted(
                set(ACTIVE_CATEGORIES) | (set(category_counts) & LEGACY_CATEGORIES),
                key=lambda code: CATEGORY_RANK[code],
            )
        ]
        periods = [
            {
                **period,
                "document_count": sum(
                    1
                    for document in documents
                    if document.year is not None
                    and period["year_from"] <= document.year <= period["year_to"]
                ),
            }
            for period in PERIODS
        ]
        return {
            "version": EXPLORER_VERSION,
            "generated_at": _utcnow(),
            "categories": categories,
            "periods": periods,
            "incubators": sorted(
                {
                    d.incubator_number
                    for d in documents
                    if d.incubator_number is not None
                }
            ),
            "languages": sorted({d.language for d in documents if d.language}),
            "documents": [_document_row(document) for document in documents],
            "documents_without_year": sum(1 for d in documents if d.year is None),
            "productive_sector": productive_sector or "all",
            "productive_sectors": sorted(
                {d.productive_sector for d in all_ready if d.productive_sector}
            ),
            "documents_excluded_by_sector": len(all_ready) - len(documents),
        }

    @staticmethod
    def _network_for_scope(
        db: Session,
        scope: ExplorerScope,
        filters: ExplorerFilters,
    ) -> tuple[list[Any], dict[str, Any]]:
        scope.validate()
        documents = _scoped_documents(db, scope)
        mentions = (
            load_db_mentions(
                status=READY_STATUS,
                document_ids=[str(document.id) for document in documents],
                db=db,
            )
            if documents
            else []
        )
        try:
            network = build_explorer_network(mentions, filters)
        except ExplorerFilterError as error:
            raise ExplorerFiltroInvalido(str(error)) from error
        if not documents:
            network["warnings"].insert(0, "No hay documentos listos en este alcance")
        return documents, network

    @staticmethod
    def network(
        db: Session,
        scope: ExplorerScope,
        filters: ExplorerFilters,
    ) -> dict[str, Any]:
        documents, network = ExplorerService._network_for_scope(db, scope, filters)
        return {
            "version": EXPLORER_VERSION,
            "generated_at": _utcnow(),
            "scope": _scope_summary(scope, documents),
            "filters": _filters_summary(filters),
            **network,
        }

    @staticmethod
    def compare(
        db: Session,
        scope: ExplorerScope,
        filters: ExplorerFilters,
        *,
        periods: Sequence[str],
        top_k: int,
    ) -> dict[str, Any]:
        if len(periods) < 2:
            raise ExplorerFiltroInvalido(
                "La comparación necesita al menos dos períodos"
            )
        unknown = [period for period in periods if period not in PERIODS_BY_ID]
        if unknown:
            raise ExplorerFiltroInvalido("Períodos desconocidos: " + ", ".join(unknown))

        # Las métricas de cada período se calculan sobre su red filtrada completa;
        # top_n no aplica aquí para no perder nodos que salen del top visible.
        full_filters = replace(filters, top_n=None)
        networks: dict[str, dict[str, Any]] = {}
        summaries: list[dict[str, Any]] = []
        ordered = sorted(periods, key=lambda period: PERIODS_BY_ID[period]["year_from"])
        for period in ordered:
            period_scope = replace(scope, period=period)
            documents, network = ExplorerService._network_for_scope(
                db, period_scope, full_filters
            )
            networks[period] = network
            summaries.append(
                {
                    "period": period,
                    "label": PERIODS_BY_ID[period]["label"],
                    "document_count": len(documents),
                    "stages": network["stages"],
                    "warnings": network["warnings"],
                }
            )

        try:
            comparison = compare_rankings(networks, filters.ranking_metric, top_k)
        except ExplorerFilterError as error:
            raise ExplorerFiltroInvalido(str(error)) from error
        return {
            "version": EXPLORER_VERSION,
            "generated_at": _utcnow(),
            "scope": {
                "incubator_number": scope.incubator_number or "all",
                "language": scope.language or "all",
                "document_ids": (
                    list(scope.document_ids) if scope.document_ids else None
                ),
                "productive_sector": scope.productive_sector or "all",
            },
            "filters": _filters_summary(filters),
            "period_summaries": summaries,
            **comparison,
        }

    @staticmethod
    def evidence(
        db: Session,
        source_id: str,
        target_id: str,
        scope: ExplorerScope,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        scope.validate()
        documents = {
            str(document.id): document for document in _scoped_documents(db, scope)
        }
        if not documents:
            raise ExplorerEvidenciaNoEncontrada(source_id, target_id)
        document_uuids = [UUID(document_id) for document_id in documents]

        def entity_sentences(canonical_id: UUID):
            return select(Entity.document_id, Entity.sentence_id).where(
                Entity.canonical_id == canonical_id,
                Entity.document_id.in_(document_uuids),
            )

        common = (
            entity_sentences(UUID(source_id))
            .intersect(entity_sentences(UUID(target_id)))
            .subquery("common_sentences")
        )
        rows = db.execute(
            select(
                Sentence.document_id,
                Sentence.sentence_id,
                Sentence.text.label("sentence_text"),
                Entity.canonical_id,
                CanonicalEntity.canonical_name,
                Entity.category,
                Entity.text.label("mention_text"),
            )
            .join(
                common,
                (Sentence.document_id == common.c.document_id)
                & (Sentence.sentence_id == common.c.sentence_id),
            )
            .join(
                Entity,
                (Entity.document_id == Sentence.document_id)
                & (Entity.sentence_id == Sentence.sentence_id),
            )
            .join(CanonicalEntity, CanonicalEntity.id == Entity.canonical_id)
            .order_by(Sentence.document_id, Sentence.sentence_id, Entity.position_start)
        ).all()

        sentences: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            document_id = str(row.document_id)
            document = documents[document_id]
            sentence = sentences.setdefault(
                (document_id, row.sentence_id),
                {
                    "document_id": document_id,
                    "document_name": document.original_filename,
                    "year": document.year,
                    "sentence_id": row.sentence_id,
                    "text": row.sentence_text,
                    "entities": [],
                },
            )
            entity = {
                "id": str(row.canonical_id),
                "name": row.canonical_name,
                "category": row.category,
                "mention_text": row.mention_text,
            }
            if entity not in sentence["entities"]:
                sentence["entities"].append(entity)

        items = list(sentences.values())
        if not items:
            raise ExplorerEvidenciaNoEncontrada(source_id, target_id)
        return {
            "source_id": source_id,
            "target_id": target_id,
            "scope": _scope_summary(scope, list(documents.values())),
            "total": len(items),
            "offset": offset,
            "limit": limit,
            "items": items[offset : offset + limit],
        }
