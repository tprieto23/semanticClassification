from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.schemas.network import IncubatorFilter


NodeStatus = Literal["pending_description", "draft", "accepted", "retired"]
ArtifactSource = Literal["official", "accepted-2026-08-25"]


class PromoteSemanticNodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projection_id: str = Field(default="prac-infra-rul-v2", pattern=r"^[a-z0-9-]+$")
    community_id: str = Field(pattern=r"^C[0-9]{3,}$")
    artifact_source: ArtifactSource
    incubator_number: IncubatorFilter = "all"
    language: Literal["es", "en", "all"] = "es"
    expected_clustering_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SemanticNodeLeidenSource(BaseModel):
    projection_id: str
    artifact_source: ArtifactSource
    incubator_number: IncubatorFilter
    language: str
    clustering_sha256: str
    source_graph_sha256: str
    generated_at: datetime | None = None
    configuration: dict
    communities: list[dict]


class SemanticNodeEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    status: NodeStatus | None = None

    @field_validator("title", "description")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("El texto no puede quedar vacío")
        return value

    @model_validator(mode="after")
    def has_changes(self):
        if not self.model_fields_set:
            raise ValueError("Se requiere al menos un campo para editar")
        return self


class SemanticNodeMemberRead(BaseModel):
    canonical_id: UUID
    canonical_name: str
    category: str


class SemanticNodeRead(BaseModel):
    id: UUID
    projection_id: str
    artifact_source: ArtifactSource
    community_id: str
    clustering_sha256: str
    source_graph_sha256: str
    scope_type: str
    scope_id: str | None
    language: str
    provenance: dict
    incubator_support: list[dict]
    document_count: int
    status: NodeStatus
    title: str | None
    description: str | None
    generation: dict | None
    members: list[SemanticNodeMemberRead]
    created_at: datetime
    updated_at: datetime


class SemanticNodeList(BaseModel):
    items: list[SemanticNodeRead]
    total: int
    skip: int
    limit: int
