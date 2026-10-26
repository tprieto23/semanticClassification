from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.analysis.explorer import PERIODS_BY_ID
from src.api.schemas.network import EdgeWeighting, IncubatorFilter
from src.categories import STORED_CATEGORIES

PeriodFilter = Literal["all", "2021-2023", "2024-2026"]
ProductiveSectorFilter = Literal["all", "Agroforestry"]
LinkMode = Literal["any", "between", "within", "pairs"]
RankingMetric = Literal[
    "pagerank",
    "degree",
    "strength",
    "betweenness",
    "closeness",
    "document_count",
]
Category = Literal[tuple(sorted(STORED_CATEGORIES))]  # type: ignore[valid-type]


class ExplorerScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incubator_number: IncubatorFilter = "all"
    language: str = Field(default="all", min_length=2, max_length=10)
    document_ids: list[UUID] | None = Field(
        default=None,
        description="Restringe el corpus a estos documentos; null usa todos los listos",
    )
    productive_sector: ProductiveSectorFilter = Field(
        default="Agroforestry",
        description="Sector productivo del corpus; 'all' incluye documentos sin sector",
    )

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "language debe ser 'all' o un identificador como es, en o pt-br"
            )
        return normalized


class ExplorerFiltersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[Category] | None = Field(
        default=None,
        description="Categorías de nodos; null usa las diez activas y el legado presente",
    )
    link_mode: LinkMode = Field(
        default="any",
        description=(
            "any: cualquier par entre las categorías; between: solo entre categorías "
            "distintas; within: solo dentro de la misma; pairs: los category_pairs dados"
        ),
    )
    category_pairs: (
        list[Annotated[list[Category], Field(min_length=2, max_length=2)]] | None
    ) = None
    minimum_node_document_count: int = Field(default=2, ge=1)
    edge_weighting: EdgeWeighting = "fractional-document"
    minimum_edge_weight: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    ranking_metric: RankingMetric = "pagerank"


class ExplorerNetworkRequest(ExplorerScopeRequest, ExplorerFiltersRequest):
    period: PeriodFilter = "all"
    top_n: int | None = Field(
        default=150,
        ge=1,
        le=5000,
        description="Cantidad de nodos a devolver según ranking_metric; null devuelve todos",
    )


class ExplorerCompareRequest(ExplorerScopeRequest, ExplorerFiltersRequest):
    periods: list[Literal["2021-2023", "2024-2026"]] = Field(
        default_factory=lambda: list(PERIODS_BY_ID), min_length=2
    )
    top_k: int = Field(default=20, ge=1, le=200)


class ExplorerCategory(BaseModel):
    code: str
    label: str
    definition: str | None
    legacy: bool
    entity_count: int


class ExplorerPeriod(BaseModel):
    id: str
    label: str
    year_from: int
    year_to: int
    document_count: int


class ExplorerDocument(BaseModel):
    id: str
    name: str
    year: int | None
    incubator_number: int | None
    language: str | None
    document_type: str | None


class ExplorerMetaResponse(BaseModel):
    version: str
    generated_at: str
    categories: list[ExplorerCategory]
    periods: list[ExplorerPeriod]
    incubators: list[int]
    languages: list[str]
    documents: list[ExplorerDocument]
    documents_without_year: int
    productive_sector: str
    productive_sectors: list[str]
    documents_excluded_by_sector: int


class ExplorerNodeMetrics(BaseModel):
    degree: int
    strength: float
    betweenness: float
    closeness: float
    pagerank: float
    document_count: int


class ExplorerNode(BaseModel):
    id: str
    name: str
    category: str
    mention_count: int
    sentence_count: int
    metrics: ExplorerNodeMetrics
    ranks: dict[str, int]
    shown_degree: int


class ExplorerEdge(BaseModel):
    source: str
    target: str
    weight: float
    sentence_count: int
    document_count: int
    category_pair: str
    confidence_tier: str


class ExplorerStageCount(BaseModel):
    nodes: int
    edges: int


class ExplorerStages(BaseModel):
    categories: list[str]
    category_pairs: list[str]
    mentions: int
    cooccurrence: ExplorerStageCount
    document_recurrence: ExplorerStageCount
    edge_weight: ExplorerStageCount
    shown: ExplorerStageCount


class ExplorerMetricProvenance(BaseModel):
    betweenness: Literal["exact", "sampled"]
    betweenness_sample_size: int | None


class ExplorerScopeSummary(BaseModel):
    period: str
    incubator_number: int | Literal["all"]
    language: str
    document_ids: list[str] | None
    productive_sector: str
    document_count: int
    documents_without_year: int


class ExplorerFiltersSummary(BaseModel):
    categories: list[str] | None
    link_mode: LinkMode
    category_pairs: list[str] | None
    minimum_node_document_count: int
    edge_weighting: str
    minimum_edge_weight: float
    ranking_metric: RankingMetric
    top_n: int | None


class ExplorerNetworkResponse(BaseModel):
    version: str
    generated_at: str
    scope: ExplorerScopeSummary
    filters: ExplorerFiltersSummary
    nodes: list[ExplorerNode]
    edges: list[ExplorerEdge]
    stages: ExplorerStages
    metric_provenance: ExplorerMetricProvenance
    warnings: list[str]


class ExplorerEntityRef(BaseModel):
    id: str
    name: str
    category: str


class ExplorerTrajectoryPoint(BaseModel):
    period: str
    rank: int | None
    value: float | None
    in_top: bool


class ExplorerTrajectory(ExplorerEntityRef):
    points: list[ExplorerTrajectoryPoint]


class ExplorerRankMove(ExplorerEntityRef):
    from_rank: int
    to_rank: int


class ExplorerPeriodChange(BaseModel):
    from_period: str
    to_period: str
    entered: list[ExplorerEntityRef]
    left: list[ExplorerEntityRef]
    moved: list[ExplorerRankMove]


class ExplorerLeader(ExplorerEntityRef):
    value: float


class ExplorerPeriodSummary(BaseModel):
    period: str
    label: str
    document_count: int
    stages: ExplorerStages
    warnings: list[str]


class ExplorerCompareScope(BaseModel):
    incubator_number: int | Literal["all"]
    language: str
    document_ids: list[str] | None
    productive_sector: str


class ExplorerCompareResponse(BaseModel):
    version: str
    generated_at: str
    scope: ExplorerCompareScope
    filters: ExplorerFiltersSummary
    metric: RankingMetric
    top_k: int
    periods: list[str]
    period_summaries: list[ExplorerPeriodSummary]
    trajectories: list[ExplorerTrajectory]
    changes: list[ExplorerPeriodChange]
    central_by_period: dict[str, dict[RankingMetric, ExplorerLeader | None]]


class ExplorerEvidenceEntity(BaseModel):
    id: str
    name: str
    category: str
    mention_text: str | None


class ExplorerEvidenceItem(BaseModel):
    document_id: str
    document_name: str
    year: int | None
    sentence_id: str
    text: str
    entities: list[ExplorerEvidenceEntity]


class ExplorerEvidenceResponse(BaseModel):
    source_id: str
    target_id: str
    scope: ExplorerScopeSummary
    total: int
    offset: int
    limit: int
    items: list[ExplorerEvidenceItem]
