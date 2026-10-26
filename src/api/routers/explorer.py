from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from src.analysis.explorer import ExplorerFilters
from src.api.schemas.explorer import (
    ExplorerCompareRequest,
    ExplorerCompareResponse,
    ExplorerEvidenceResponse,
    ExplorerFiltersRequest,
    ExplorerMetaResponse,
    ExplorerNetworkRequest,
    ExplorerNetworkResponse,
    ExplorerScopeRequest,
    PeriodFilter,
    ProductiveSectorFilter,
)
from src.api.schemas.network import IncubatorFilter
from src.models.database import get_db
from src.services.explorer import ExplorerScope, ExplorerService

router = APIRouter(prefix="/analysis/explorer/v1", tags=["Explorer"])


def _scope(selection: ExplorerScopeRequest, period: str | None = None) -> ExplorerScope:
    return ExplorerScope(
        period=None if period in (None, "all") else period,
        incubator_number=(
            None if selection.incubator_number == "all" else selection.incubator_number
        ),
        language=None if selection.language == "all" else selection.language,
        document_ids=(
            tuple(str(document_id) for document_id in selection.document_ids)
            if selection.document_ids is not None
            else None
        ),
        productive_sector=(
            None
            if selection.productive_sector == "all"
            else selection.productive_sector
        ),
    )


def _filters(selection: ExplorerFiltersRequest, top_n: int | None) -> ExplorerFilters:
    return ExplorerFilters(
        categories=tuple(selection.categories) if selection.categories else None,
        link_mode=selection.link_mode,
        category_pairs=(
            tuple((pair[0], pair[1]) for pair in selection.category_pairs)
            if selection.category_pairs
            else None
        ),
        minimum_node_document_count=selection.minimum_node_document_count,
        edge_weighting=selection.edge_weighting,
        minimum_edge_weight=selection.minimum_edge_weight,
        ranking_metric=selection.ranking_metric,
        top_n=top_n,
    )


@router.get("/meta", response_model=ExplorerMetaResponse)
def explorer_meta(
    productive_sector: Annotated[ProductiveSectorFilter, Query()] = "Agroforestry",
    db: Session = Depends(get_db),
):
    return ExplorerService.meta(
        db, None if productive_sector == "all" else productive_sector
    )


@router.post("/network", response_model=ExplorerNetworkResponse)
def explorer_network(
    body: ExplorerNetworkRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    selection = body or ExplorerNetworkRequest()
    return ExplorerService.network(
        db,
        _scope(selection, selection.period),
        _filters(selection, selection.top_n),
    )


@router.post("/compare", response_model=ExplorerCompareResponse)
def explorer_compare(
    body: ExplorerCompareRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    selection = body or ExplorerCompareRequest()
    return ExplorerService.compare(
        db,
        _scope(selection),
        _filters(selection, top_n=None),
        periods=selection.periods,
        top_k=selection.top_k,
    )


@router.get("/evidence", response_model=ExplorerEvidenceResponse)
def explorer_evidence(
    source_id: UUID,
    target_id: UUID,
    period: Annotated[PeriodFilter, Query()] = "all",
    incubator_number: Annotated[IncubatorFilter, Query()] = "all",
    language: Annotated[str, Query(min_length=2, max_length=10)] = "all",
    document_ids: Annotated[list[UUID] | None, Query()] = None,
    productive_sector: Annotated[ProductiveSectorFilter, Query()] = "Agroforestry",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    db: Session = Depends(get_db),
):
    selection = ExplorerScopeRequest(
        incubator_number=incubator_number,
        language=language,
        document_ids=document_ids,
        productive_sector=productive_sector,
    )
    return ExplorerService.evidence(
        db,
        str(source_id),
        str(target_id),
        _scope(selection, period),
        offset=offset,
        limit=limit,
    )
