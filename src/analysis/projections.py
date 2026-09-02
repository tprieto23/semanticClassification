"""Definiciones versionadas de proyecciones analíticas y sus vistas."""

from __future__ import annotations

from dataclasses import dataclass

from src.analysis.cooccurrence import SEMANTIC_CORE_CATEGORIES, all_category_pairs

SEMANTIC_PROJECTION_ID = "prac-infra-gov-v1"
SEMANTIC_CORE_PAIRS = all_category_pairs(SEMANTIC_CORE_CATEGORIES)


@dataclass(frozen=True)
class ProjectionView:
    view_id: str
    label: str
    node_categories: tuple[str, ...]
    category_pairs: tuple[tuple[str, str], ...]

    @property
    def category_pair_labels(self) -> tuple[str, ...]:
        return tuple("--".join(pair) for pair in self.category_pairs)


@dataclass(frozen=True)
class ProjectionDefinition:
    projection_id: str
    label: str
    node_categories: tuple[str, ...]
    category_pairs: tuple[tuple[str, str], ...]
    views: tuple[ProjectionView, ...]

    @property
    def category_pair_labels(self) -> tuple[str, ...]:
        return tuple("--".join(pair) for pair in self.category_pairs)


_CROSS_PAIRS = tuple(pair for pair in SEMANTIC_CORE_PAIRS if pair[0] != pair[1])
_INTRA_PAIRS = tuple(pair for pair in SEMANTIC_CORE_PAIRS if pair[0] == pair[1])

SEMANTIC_PROJECTION = ProjectionDefinition(
    projection_id=SEMANTIC_PROJECTION_ID,
    label="Red semántica tipada PRAC + INFRA + GOV",
    node_categories=SEMANTIC_CORE_CATEGORIES,
    category_pairs=SEMANTIC_CORE_PAIRS,
    views=(
        ProjectionView(
            "all",
            "Red completa: seis tipos de relación",
            SEMANTIC_CORE_CATEGORIES,
            SEMANTIC_CORE_PAIRS,
        ),
        ProjectionView(
            "cross",
            "Relaciones entre categorías distintas",
            SEMANTIC_CORE_CATEGORIES,
            _CROSS_PAIRS,
        ),
        ProjectionView(
            "intra",
            "Relaciones dentro de la misma categoría",
            SEMANTIC_CORE_CATEGORIES,
            _INTRA_PAIRS,
        ),
        ProjectionView("prac-prac", "PRAC–PRAC", ("PRAC",), (("PRAC", "PRAC"),)),
        ProjectionView(
            "infra-infra", "INFRA–INFRA", ("INFRA",), (("INFRA", "INFRA"),)
        ),
        ProjectionView("gov-gov", "GOV–GOV", ("GOV",), (("GOV", "GOV"),)),
        ProjectionView(
            "prac-infra",
            "PRAC–INFRA",
            ("PRAC", "INFRA"),
            (("PRAC", "INFRA"),),
        ),
        ProjectionView(
            "prac-gov", "PRAC–GOV", ("PRAC", "GOV"), (("PRAC", "GOV"),)
        ),
        ProjectionView(
            "infra-gov",
            "INFRA–GOV",
            ("INFRA", "GOV"),
            (("INFRA", "GOV"),),
        ),
    ),
)

PROJECTIONS = {SEMANTIC_PROJECTION_ID: SEMANTIC_PROJECTION}


def get_projection(projection_id: str) -> ProjectionDefinition | None:
    return PROJECTIONS.get(projection_id)


def projection_manifest(projection: ProjectionDefinition) -> dict:
    return {
        "id": projection.projection_id,
        "label": projection.label,
        "node_categories": list(projection.node_categories),
        "category_pairs": list(projection.category_pair_labels),
        "views": [
            {
                "id": view.view_id,
                "label": view.label,
                "node_categories": list(view.node_categories),
                "category_pairs": list(view.category_pair_labels),
            }
            for view in projection.views
        ],
    }
