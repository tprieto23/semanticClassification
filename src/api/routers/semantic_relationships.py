from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from src.api.schemas.semantic_relationships import (
    MetaRelationshipBuildRequest,
    MetaRelationshipBuildResponse,
    MetaRelationshipRead,
    MetaNetworkGraphMLExportRequest,
    MetaNetworkGraphMLExportResponse,
)
from src.models.database import get_db
from src.services.semantic_relationships import SemanticRelationshipService

router = APIRouter(prefix="/semantic-network", tags=["Semantic network"])


@router.post(
    "/relationships/build",
    response_model=MetaRelationshipBuildResponse,
    status_code=status.HTTP_200_OK,
)
def build_relationships(
    body: MetaRelationshipBuildRequest,
    db: Session = Depends(get_db),
):
    return SemanticRelationshipService.build(
        db,
        projection_id=body.projection_id,
        artifact_source=body.artifact_source,
        clustering_sha256=body.clustering_sha256,
        incubator_number=(
            None if body.incubator_number == "all" else body.incubator_number
        ),
        language=body.language,
        minimum_source_edge_weight=body.minimum_source_edge_weight,
        require_accepted_nodes=body.require_accepted_nodes,
        force_recompute=body.force_recompute,
    )


@router.get("/relationships", response_model=list[MetaRelationshipRead])
def list_relationships(
    clustering_sha256: Annotated[str, Query(pattern=r"^[0-9a-f]{64}$")],
    minimum_source_edge_weight: Annotated[float, Query(ge=0)] = 0.0,
    db: Session = Depends(get_db),
):
    return SemanticRelationshipService.list(
        db,
        clustering_sha256=clustering_sha256,
        minimum_source_edge_weight=minimum_source_edge_weight,
    )


@router.post("/export/graphml", response_model=MetaNetworkGraphMLExportResponse)
def export_graphml(
    body: MetaNetworkGraphMLExportRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    payload = SemanticRelationshipService.export_graphml(
        db,
        clustering_sha256=body.clustering_sha256,
        minimum_source_edge_weight=body.minimum_source_edge_weight,
        include_isolates=body.include_isolates,
    )
    payload["graphml_url"] = (
        f"{str(request.base_url).rstrip('/')}/files/graphs/{payload['graphml_path']}"
    )
    return payload
