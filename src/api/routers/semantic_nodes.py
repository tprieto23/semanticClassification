from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.api.schemas.semantic_nodes import (
    NodeStatus,
    ArtifactSource,
    PromoteSemanticNodeRequest,
    SemanticNodeLeidenSource,
    SemanticNodeEdit,
    SemanticNodeList,
    SemanticNodeRead,
)
from src.api.schemas.network import IncubatorFilter
from src.models.database import get_db
from src.services.semantic_nodes import SemanticNodeService

router = APIRouter(prefix="/semantic-nodes", tags=["Semantic nodes"])


@router.get("/leiden-source", response_model=SemanticNodeLeidenSource)
def get_leiden_source(
    projection_id: Annotated[str, Query(pattern=r"^[a-z0-9-]+$")] = "prac-infra-gov-v1",
    artifact_source: ArtifactSource = "official",
    incubator_number: IncubatorFilter = "all",
    language: Annotated[str, Query(pattern=r"^(es|en|all)$")] = "es",
):
    return SemanticNodeService.leiden_source(
        projection_id=projection_id,
        artifact_source=artifact_source,
        incubator_number=(None if incubator_number == "all" else incubator_number),
        language=language,
    )


@router.post("/from-leiden", response_model=SemanticNodeRead,
             status_code=status.HTTP_201_CREATED)
def promote_from_leiden(body: PromoteSemanticNodeRequest, db: Session = Depends(get_db)):
    return SemanticNodeService.promote(
        db,
        projection_id=body.projection_id,
        artifact_source=body.artifact_source,
        community_id=body.community_id,
        incubator_number=(
            None if body.incubator_number == "all" else body.incubator_number
        ),
        language=body.language,
        expected_hash=body.expected_clustering_sha256,
    )


@router.get("", response_model=SemanticNodeList)
def list_semantic_nodes(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    status: NodeStatus | None = None,
    incubator_number: Annotated[int | None, Query(ge=1, le=8)] = None,
    db: Session = Depends(get_db),
):
    return SemanticNodeService.list(
        db, skip=skip, limit=limit, status=status,
        incubator_number=incubator_number,
    )


@router.get("/{node_id}", response_model=SemanticNodeRead)
def get_semantic_node(node_id: UUID, db: Session = Depends(get_db)):
    return SemanticNodeService.get(db, node_id)


@router.patch("/{node_id}", response_model=SemanticNodeRead)
def edit_semantic_node(
    node_id: UUID, body: SemanticNodeEdit, db: Session = Depends(get_db)
):
    return SemanticNodeService.edit(db, node_id, body.model_dump(exclude_unset=True))


@router.post("/{node_id}/generate-description", response_model=SemanticNodeRead)
def generate_semantic_node_description(
    node_id: UUID, db: Session = Depends(get_db)
):
    return SemanticNodeService.generate(db, node_id)
