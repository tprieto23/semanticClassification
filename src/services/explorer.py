"""Servicio de lectura para el explorador interactivo de entidades.

No escribe en PostgreSQL ni en ``s3/``: consulta documentos listos y sus
menciones canonicalizadas y delega la construcción de la red en
:mod:`src.analysis.explorer`.

Las redes con métricas se guardan en una caché en memoria por proceso. La
clave combina los documentos del alcance, una huella de sus menciones y los
filtros estructurales, así que ``top_n`` y ``ranking_metric`` reutilizan la
red ya calculada. Ver "Caché del explorador" en ``.agent/context/architecture.md``.
"""

from __future__ import annotations

import threading
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable, Hashable, Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.analysis.cooccurrence import CATEGORY_RANK, load_db_mentions
from src.analysis.explorer import (
    CATEGORY_LABELS,
    EXPLORER_VERSION,
    PERIODS,
    PERIODS_BY_ID,
    RANKING_METRICS,
    ExplorerFilterError,
    ExplorerFilters,
    RankedNetwork,
    build_ranked_network,
    compare_rankings,
    select_shown_network,
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

# Una red ocupa alrededor de 1 KB por link: unos 14 MB con los filtros por
# defecto y unos 90 MB con recurrencia 1. El presupuesto de links limita la
# memoria de cada worker a unos 300 MB aunque se guarden redes grandes.
RANKED_CACHE_MAX_ENTRIES = 16
RANKED_CACHE_MAX_EDGES = 300_000
# La huella no detecta un cambio de nombre canónico sin cambio de menciones;
# el vencimiento acota cuánto puede durar ese caso.
RANKED_CACHE_TTL_SECONDS = 30 * 60


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
    # Con mode "exclude" se quitan solo los documentos de ese tipo; los que no
    # tienen tipo se conservan.
    document_type: str | None = None
    document_type_mode: str = "only"
    document_ids: tuple[str, ...] | None = None
    productive_sector: str | None = DEFAULT_PRODUCTIVE_SECTOR

    def validate(self) -> None:
        if self.period is not None and self.period not in PERIODS_BY_ID:
            raise ExplorerFiltroInvalido(
                f"Período desconocido: {self.period!r}. Use 'all' o uno de: "
                + ", ".join(PERIODS_BY_ID)
            )


class RankedNetworkCache:
    """Caché LRU con vencimiento, segura entre hilos, de redes con métricas.

    Descarta las redes usadas hace más tiempo cuando se supera la cantidad de
    entradas o la suma de links; la red recién calculada siempre se conserva.
    FastAPI ejecuta los endpoints síncronos en un pool de hilos: si llegan dos
    peticiones con la misma clave, la segunda espera a la primera en lugar de
    repetir el cálculo. Los errores no se guardan.
    """

    def __init__(
        self,
        max_entries: int,
        ttl_seconds: float,
        max_edges: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._max_entries = max_entries
        self._max_edges = max_edges
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[Hashable, tuple[float, RankedNetwork]] = (
            OrderedDict()
        )
        self._lock = threading.Lock()
        self._building: dict[Hashable, threading.Lock] = {}

    @staticmethod
    def _size(value: RankedNetwork) -> int:
        return value.graph.number_of_edges()

    def _over_budget(self) -> bool:
        if len(self._entries) > self._max_entries:
            return True
        if self._max_edges is None:
            return False
        stored = sum(self._size(value) for _, value in self._entries.values())
        return stored > self._max_edges

    def _fresh(self, key: Hashable) -> RankedNetwork | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def get_or_build(
        self, key: Hashable, build: Callable[[], RankedNetwork]
    ) -> RankedNetwork:
        with self._lock:
            value = self._fresh(key)
            if value is not None:
                return value
            key_lock = self._building.setdefault(key, threading.Lock())

        with key_lock:
            with self._lock:
                value = self._fresh(key)
                if value is not None:
                    return value
            try:
                value = build()
            finally:
                with self._lock:
                    self._building.pop(key, None)
            with self._lock:
                self._entries[key] = (self._clock() + self._ttl_seconds, value)
                self._entries.move_to_end(key)
                while len(self._entries) > 1 and self._over_budget():
                    self._entries.popitem(last=False)
            return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


_RANKED_NETWORKS = RankedNetworkCache(
    RANKED_CACHE_MAX_ENTRIES,
    RANKED_CACHE_TTL_SECONDS,
    max_edges=RANKED_CACHE_MAX_EDGES,
)


def _data_fingerprint(db: Session, documents: Sequence[Any]) -> tuple[Any, ...]:
    """Huella barata de las menciones del alcance.

    Cambia si se agregan, borran o reprocesan menciones, o si cambia su
    asignación a entidades canónicas.
    """

    if not documents:
        return ()
    row = db.execute(
        select(
            func.count(Entity.id),
            func.count(func.distinct(Entity.canonical_id)),
            func.max(Entity.created_at),
        ).where(Entity.document_id.in_([document.id for document in documents]))
    ).one()
    return tuple(row)


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
    if scope.document_type is not None:
        if scope.document_type_mode == "exclude":
            statement = statement.where(
                or_(
                    Document.document_type.is_(None),
                    Document.document_type != scope.document_type,
                )
            )
        else:
            statement = statement.where(Document.document_type == scope.document_type)
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
        "document_type": scope.document_type,
        "document_type_mode": scope.document_type_mode,
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
        "excluded_entity_ids": list(filters.excluded_entity_ids) or None,
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
            "document_types": [
                {"name": name, "document_count": count}
                for name, count in sorted(
                    Counter(
                        d.document_type for d in documents if d.document_type
                    ).items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ],
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
        if filters.ranking_metric not in RANKING_METRICS:
            raise ExplorerFiltroInvalido(
                f"ranking_metric no soportada: {filters.ranking_metric!r}"
            )
        documents = _scoped_documents(db, scope)
        document_ids = [str(document.id) for document in documents]
        structural = filters.structural()

        def build() -> RankedNetwork:
            mentions = (
                load_db_mentions(status=READY_STATUS, document_ids=document_ids, db=db)
                if documents
                else []
            )
            return build_ranked_network(mentions, structural)

        # El conjunto de documentos, y no el alcance pedido, define la red: dos
        # alcances que seleccionan los mismos documentos comparten resultado.
        key = (
            tuple(sorted(document_ids)),
            _data_fingerprint(db, documents),
            structural,
        )
        try:
            ranked = _RANKED_NETWORKS.get_or_build(key, build)
            network = select_shown_network(
                ranked, filters.ranking_metric, filters.top_n
            )
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
                "document_type": scope.document_type,
                "document_type_mode": scope.document_type_mode,
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
