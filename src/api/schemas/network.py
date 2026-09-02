from datetime import datetime
from typing import Annotated, Literal

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
    generated_at: datetime
    scope: str
    filters: NetworkFilters
    minimum_weight: int
    includes_isolates: bool
    coverage: NetworkCoverage
    counts: NetworkCounts
    nodes_by_category: dict[str, int]
    category_pair_summary: list[CategoryPairSummary]
    top_nodes_by_strength: list[TopNetworkNode]
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


class NetworkViewCounts(BaseModel):
    canonical_nodes: int
    undirected_edges: int
    components: int
    edge_observations: int
    max_edge_weight: int


class NetworkViewSummary(NetworkViewDefinition):
    counts: NetworkViewCounts
    nodes_by_category: dict[str, int]
    edges_by_category_pair: dict[str, int]
    outputs: dict[str, str]


class TypedNetworkCounts(NetworkCounts):
    source_mentions: int
    projected_mentions: int
    context_mentions_in_projected_sentences: int
    sentence_entity_presences: int
    sentences_with_edges: int


class TypedNetworkBuildResponse(BaseModel):
    generated_at: datetime
    scope: str
    projection: NetworkProjectionDefinition
    view: NetworkViewDefinition
    filters: NetworkFilters
    minimum_weight: int
    includes_isolates: bool
    coverage: NetworkCoverage
    counts: TypedNetworkCounts
    nodes_by_category: dict[str, int]
    category_pair_summary: list[CategoryPairSummary]
    top_nodes_by_strength: list[TopNetworkNode]
    outputs: dict[str, str]
    views: dict[str, NetworkViewSummary]


class BackboneGraphCounts(BaseModel):
    canonical_nodes: int
    undirected_edges: int
    components: int
    component_sizes: list[int]
    nodes_by_category: dict[str, int]
    edges_by_category_pair: dict[str, int]
    edges_by_confidence_tier: dict[str, int]
    max_analysis_weight: float


class BackboneBaseCounts(BaseModel):
    canonical_nodes: int
    edge_incident_nodes: int
    isolated_nodes: int
    undirected_edges: int
    sentences: int
    edge_observations: int


class BackboneEligibility(BaseModel):
    eligible_nodes_before_edge_induction: int
    excluded_nodes: int
    excluded_edges: int


class BackboneViewSummary(NetworkViewDefinition):
    counts: BackboneGraphCounts
    outputs: dict[str, str]


class AnalyticalNetworkBuildResponse(BaseModel):
    generated_at: datetime
    scope: str
    filters: NetworkFilters
    projection_id: str
    construction: DocumentRecurrentCoreConstruction
    definitions: dict[str, str]
    base_network: BackboneBaseCounts
    eligibility: BackboneEligibility
    analytical_network: BackboneGraphCounts
    main_component: BackboneGraphCounts
    primary_component_scope: Literal["all-components", "main-component"]
    primary_view: BackboneViewSummary
    component_views: dict[str, dict[str, BackboneViewSummary]]
    coverage: NetworkCoverage
    outputs: dict[str, str]


class LeidenSourceGraph(BaseModel):
    component_scope: ComponentScope
    view: NetworkViewDefinition
    graphml_sha256: str
    canonical_nodes: int
    undirected_edges: int
    outputs: dict[str, str]


class LeidenClusteringCounts(BaseModel):
    communities: int
    singleton_communities: int
    largest_community_size: int
    smallest_community_size: int


class LeidenClusteringResponse(BaseModel):
    generated_at: datetime
    status: Literal["completed", "trivial", "empty"]
    cached: bool
    scope: str
    filters: NetworkFilters
    projection_id: str
    construction: DocumentRecurrentCoreConstruction
    configuration: LeidenConfiguration
    algorithm_versions: dict[str, str]
    source: LeidenSourceGraph
    counts: LeidenClusteringCounts
    community_sizes: list[int]
    objective_quality: float
    modularity: float
    definitions: dict[str, str]
    warnings: list[str]
    outputs: dict[str, str]


class ProjectionViewsResponse(BaseModel):
    projection: NetworkProjectionDefinition
    views: list[NetworkViewDefinition]


class SentenceEvidenceEntity(BaseModel):
    canonical_id: str
    canonical_name: str
    category: str
    is_projected: bool
    mention_count: int
    texts: list[str]
    ambiguities: list[str]


class EdgeEvidenceItem(BaseModel):
    document_id: str
    sentence_id: str
    context: str
    pair_context: str
    projected_entities: list[SentenceEvidenceEntity]
    context_entities: list[SentenceEvidenceEntity]


class EdgeEvidenceSummary(BaseModel):
    source_canonical_id: str
    target_canonical_id: str
    source_name: str
    target_name: str
    category_pair: str
    weight: int
    document_count: int


class EdgeEvidenceResponse(BaseModel):
    projection_id: str
    scope: str
    edge: EdgeEvidenceSummary
    total: int
    offset: int
    limit: int
    items: list[EdgeEvidenceItem]
