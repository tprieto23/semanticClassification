from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy.orm import Session

from src.api.schemas.network import (
    AnalyticalNetworkBuildResponse,
    EdgeEvidenceResponse,
    IncubatorFilter,
    LeidenClusteringRequest,
    LeidenClusteringResponse,
    NetworkBuildRequest,
    NetworkBuildResponse,
    ProjectionViewsResponse,
    TypedNetworkBuildRequest,
    TypedNetworkBuildResponse,
)
from src.models.database import get_db
from src.services.network import NetworkService

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post("/network", response_model=NetworkBuildResponse)
def build_network(
    request: Request,
    body: NetworkBuildRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    selection = body or NetworkBuildRequest()
    incubator_number = (
        None if selection.incubator_number == "all" else selection.incubator_number
    )
    language = None if selection.language == "all" else selection.language
    payload = NetworkService.build(
        db,
        minimum_weight=selection.minimum_weight,
        include_isolates=selection.include_isolates,
        incubator_number=incubator_number,
        language=language,
    )
    return NetworkService.with_public_urls(payload, str(request.base_url))


@router.get("/network/latest", response_model=NetworkBuildResponse)
def latest_network(
    request: Request,
    minimum_weight: Annotated[int, Query(ge=1)] = 1,
    include_isolates: bool = True,
    incubator_number: Annotated[IncubatorFilter, Query()] = "all",
    language: Annotated[str, Query(min_length=2, max_length=10)] = "all",
):
    selection = NetworkBuildRequest(
        incubator_number=incubator_number,
        language=language,
        minimum_weight=minimum_weight,
        include_isolates=include_isolates,
    )
    payload = NetworkService.latest(
        minimum_weight=selection.minimum_weight,
        include_isolates=selection.include_isolates,
        incubator_number=(
            None if selection.incubator_number == "all" else selection.incubator_number
        ),
        language=None if selection.language == "all" else selection.language,
    )
    return NetworkService.with_public_urls(payload, str(request.base_url))


@router.post(
    "/network/projections/{projection_id}",
    response_model=TypedNetworkBuildResponse | AnalyticalNetworkBuildResponse,
)
def build_typed_projection(
    projection_id: str,
    request: Request,
    body: TypedNetworkBuildRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    selection = body or TypedNetworkBuildRequest()
    payload = NetworkService.build_projection(
        db,
        projection_id,
        minimum_weight=selection.minimum_weight,
        include_isolates=selection.include_isolates,
        incubator_number=(
            None if selection.incubator_number == "all" else selection.incubator_number
        ),
        language=None if selection.language == "all" else selection.language,
        construction=(
            selection.construction.model_dump()
            if selection.construction is not None
            else None
        ),
    )
    return NetworkService.with_public_urls(payload, str(request.base_url))


@router.post(
    "/network/projections/{projection_id}/clusterings/leiden",
    response_model=LeidenClusteringResponse,
)
def cluster_typed_projection_with_leiden(
    projection_id: str,
    body: LeidenClusteringRequest,
    request: Request,
):
    payload = NetworkService.cluster_projection_leiden(
        projection_id,
        construction=body.construction.model_dump(),
        component_scope=body.component_scope,
        view_id=body.view,
        configuration=body.configuration.model_dump(),
        force_recompute=body.force_recompute,
        incubator_number=(
            None if body.incubator_number == "all" else body.incubator_number
        ),
        language=None if body.language == "all" else body.language,
    )
    return NetworkService.with_public_urls(payload, str(request.base_url))


@router.get(
    "/network/projections/{projection_id}/latest",
    response_model=TypedNetworkBuildResponse,
)
def latest_typed_projection(
    projection_id: str,
    request: Request,
    minimum_weight: Annotated[int, Query(ge=1)] = 1,
    include_isolates: bool = True,
    incubator_number: Annotated[IncubatorFilter, Query()] = "all",
    language: Annotated[str, Query(min_length=2, max_length=10)] = "all",
):
    selection = NetworkBuildRequest(
        incubator_number=incubator_number,
        language=language,
        minimum_weight=minimum_weight,
        include_isolates=include_isolates,
    )
    payload = NetworkService.latest_projection(
        projection_id,
        minimum_weight=selection.minimum_weight,
        include_isolates=selection.include_isolates,
        incubator_number=(
            None if selection.incubator_number == "all" else selection.incubator_number
        ),
        language=None if selection.language == "all" else selection.language,
    )
    return NetworkService.with_public_urls(payload, str(request.base_url))


@router.get(
    "/network/projections/{projection_id}/views",
    response_model=ProjectionViewsResponse,
)
def typed_projection_views(projection_id: str):
    return NetworkService.projection_views(projection_id)


@router.get(
    "/network/projections/{projection_id}/edges/{source_id}/{target_id}/evidence",
    response_model=EdgeEvidenceResponse,
)
def typed_edge_evidence(
    projection_id: str,
    source_id: str,
    target_id: str,
    minimum_weight: Annotated[int, Query(ge=1)] = 1,
    include_isolates: bool = True,
    incubator_number: Annotated[IncubatorFilter, Query()] = "all",
    language: Annotated[str, Query(min_length=2, max_length=10)] = "all",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    db: Session = Depends(get_db),
):
    selection = NetworkBuildRequest(
        incubator_number=incubator_number,
        language=language,
        minimum_weight=minimum_weight,
        include_isolates=include_isolates,
    )
    return NetworkService.edge_evidence(
        db,
        projection_id,
        source_id,
        target_id,
        minimum_weight=selection.minimum_weight,
        include_isolates=selection.include_isolates,
        incubator_number=(
            None if selection.incubator_number == "all" else selection.incubator_number
        ),
        language=None if selection.language == "all" else selection.language,
        offset=offset,
        limit=limit,
    )
