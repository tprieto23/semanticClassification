from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.api.schemas.semantic_nodes import ArtifactSource
from src.api.schemas.network import IncubatorFilter


class MetaRelationshipBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projection_id: str = Field(default="prac-infra-gov-v1", pattern=r"^[a-z0-9-]+$")
    artifact_source: ArtifactSource
    clustering_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    incubator_number: IncubatorFilter = "all"
    language: Literal["es", "en", "all"] = "es"
    minimum_source_edge_weight: float = Field(default=0.0, ge=0.0)
    require_accepted_nodes: bool = True
    force_recompute: bool = False


class MetaRelationshipRead(BaseModel):
    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    source_community_id: str
    target_community_id: str
    source_title: str | None
    target_title: str | None
    source_edge_count: int
    weight: float
    mean_source_weight: float
    sentence_support_sum: int
    document_support_sum: int
    formula_version: str
    minimum_source_edge_weight: float
    status: str


class MetaRelationshipBuildResponse(BaseModel):
    generated_at: datetime
    projection_id: str
    artifact_source: ArtifactSource
    clustering_sha256: str
    source_graph_sha256: str
    formula_version: str
    parameters: dict
    counts: dict[str, int]
    cached: bool
    relationships: list[MetaRelationshipRead]


class MetaNetworkGraphMLExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clustering_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    minimum_source_edge_weight: float = Field(default=0.0, ge=0.0)
    include_isolates: bool = True


class MetaNetworkGraphMLExportResponse(BaseModel):
    generated_at: datetime
    clustering_sha256: str
    formula_version: str
    minimum_source_edge_weight: float
    include_isolates: bool
    counts: dict[str, int]
    graphml_path: str
    graphml_url: str
    graphml_sha256: str
