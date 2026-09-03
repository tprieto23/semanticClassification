from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

IncubatorFilter = Literal["all"] | Annotated[int, Field(ge=1, le=8)]
EdgeWeighting = Literal[
    "sentence-count",
    "document-count",
    "fractional",
    "fractional-document",
]
LeidenObjective = Literal["modularity", "cpm"]
LeidenWeightAttribute = Literal[
    "none",
    "weight",
    "analysis_weight",
    "sentence_count",
    "document_count",
    "fractional_weight",
    "fractional_document_weight",
]
ComponentScope = Literal["all-components", "main-component"]


class RawThresholdConstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["raw-threshold-v1"]
    minimum_weight: int = Field(default=1, ge=1)
    include_isolates: bool = True


class DocumentRecurrentCoreConstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["document-recurrent-core-v1"]
    minimum_node_document_count: int = Field(default=2, ge=1)
    edge_weighting: EdgeWeighting = "fractional-document"
    include_minor_components: bool = True


NetworkConstruction = Annotated[
    RawThresholdConstruction | DocumentRecurrentCoreConstruction,
    Field(discriminator="method"),
]


class NetworkBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incubator_number: IncubatorFilter = "all"
    language: str = Field(default="all", min_length=2, max_length=10)
    minimum_weight: int = Field(default=1, ge=1)
    include_isolates: bool = True

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "language debe ser 'all' o un identificador como es, en o pt-br"
            )
        return normalized


class TypedNetworkBuildRequest(NetworkBuildRequest):
    construction: NetworkConstruction | None = None


class LeidenConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["leiden-v1"] = "leiden-v1"
    objective_function: LeidenObjective = "modularity"
    resolution: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    iterations: int = -1
    weight_attribute: LeidenWeightAttribute = "weight"

    @field_validator("iterations")
    @classmethod
    def validate_iterations(cls, value: int) -> int:
        if value != -1 and value < 1:
            raise ValueError("iterations debe ser -1 o un entero mayor que 0")
        return value


class LeidenClusteringRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incubator_number: IncubatorFilter = "all"
    language: str = Field(default="all", min_length=2, max_length=10)
    construction: DocumentRecurrentCoreConstruction
    component_scope: ComponentScope = "main-component"
    view: str = Field(default="all", pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    configuration: LeidenConfiguration = Field(default_factory=LeidenConfiguration)
    force_recompute: bool = False

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "language debe ser 'all' o un identificador como es, en o pt-br"
            )
        return normalized


class NetworkFilters(BaseModel):
    incubator_number: IncubatorFilter
    language: str


class NetworkCoverage(BaseModel):
    documents_included: int
    documents_total: int
    excluded_by_status: dict[str, int]


class NetworkCounts(BaseModel):
    mentions: int
    canonical_nodes: int
    sentences: int
    undirected_edges: int
    edge_observations: int
    max_edge_weight: int
    components: int


class CategoryPairSummary(BaseModel):
    source_category: str
    target_category: str
    source_nodes: int
    target_nodes: int
    possible_pairs: int
    observed_edges: int
    density: float
    total_sentence_cooccurrences: int
    mean_weight_observed_edges: float
    max_weight: int


class TopNetworkNode(BaseModel):
    canonical_id: str
    canonical_name: str
    category: str
    degree: int
    strength: int


class NetworkBuildResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_at: datetime
    scope: str
    filters: dict[str, Any]
    counts: dict[str, Any]
    outputs: dict[str, str]


class NetworkProjectionDefinition(BaseModel):
    id: str
    label: str
    node_categories: list[str]
    category_pairs: list[str]


class NetworkViewDefinition(BaseModel):
    id: str
    label: str
    node_categories: list[str]
    category_pairs: list[str]


class TypedNetworkBuildResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_at: datetime
    scope: str
    projection: NetworkProjectionDefinition
    filters: dict[str, Any]
    counts: dict[str, Any]
    outputs: dict[str, str]


class AnalyticalNetworkBuildResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_at: datetime
    scope: str
    projection_id: str
    filters: dict[str, Any]
    configuration: dict[str, Any]
    counts: dict[str, Any]
    outputs: dict[str, str]


class LeidenClusteringResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_at: datetime
    scope: str
    projection_id: str
    configuration: dict[str, Any]
    counts: dict[str, Any]
    outputs: dict[str, str]


class ProjectionViewsResponse(BaseModel):
    projection: NetworkProjectionDefinition
    views: list[NetworkViewDefinition]


class EdgeEvidenceEntity(BaseModel):
    canonical_id: str
    canonical_name: str
    category: str
    is_projected: bool
    mention_text: str | None = None
    ambiguity: str | None = None


class EdgeEvidenceItem(BaseModel):
    document_id: str
    sentence_id: str
    context: str
    projected_entities: list[EdgeEvidenceEntity]
    context_entities: list[EdgeEvidenceEntity]


class EdgeEvidenceResponse(BaseModel):
    projection_id: str
    scope: str
    edge: dict[str, str]
    total: int
    offset: int
    limit: int
    items: list[EdgeEvidenceItem]
