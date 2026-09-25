"""Helpers deterministas para la nueva carpetización de grafos.

La estructura es:

    s3/graphs/
      ├── graphml/
      ├── json/
      └── csv/
            ├── corpus/{lang}/
            ├── incubators/{incubator_number}/{lang}/
            └── documents/{document_id}/

Los parámetros de construcción viven en el JSON de metadatos. Los nombres de
archivo son estables para que cada ejecución reemplace el artefacto oficial.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from src.config import settings

SCOPE_TYPES = {"corpus", "incubators", "documents"}
LANGUAGES = {"es", "en", "all"}


def _validate_language(language: str) -> str:
    lang = language or "all"
    if lang not in LANGUAGES:
        raise ValueError(f"Idioma no soportado: {lang}")
    return lang


def graph_scope_dir(
    scope_type: str,
    scope_id: str | int | UUID | None,
    language: str,
) -> Path:
    """Devuelve el directorio relativo al scope, sin el formato raíz."""
    if scope_type not in SCOPE_TYPES:
        raise ValueError(f"Tipo de alcance no soportado: {scope_type}")

    lang = _validate_language(language)

    if scope_type == "corpus":
        return Path("corpus") / lang
    if scope_type == "incubators":
        if scope_id is None:
            raise ValueError("incubators requiere scope_id")
        return Path("incubators") / str(scope_id) / lang
    if scope_type == "documents":
        if scope_id is None:
            raise ValueError("documents requiere scope_id")
        return Path("documents") / str(scope_id)
    return Path()  # pragma: no cover


def base_dir(
    format: str, scope_type: str, scope_id: str | int | UUID | None, language: str
) -> Path:
    """Devuelve el directorio absoluto para un formato y scope."""
    if format not in {"graphml", "json", "csv"}:
        raise ValueError(f"Formato no soportado: {format}")
    return (
        settings.STORAGE_GRAPHS
        / format
        / graph_scope_dir(scope_type, scope_id, language)
    )


def red_plana_filename(minimum_weight: int, include_isolates: bool) -> str:
    """Nombre oficial estable para la red principal."""
    if minimum_weight < 1:
        raise ValueError("minimum_weight debe ser al menos 1")
    return "main_network"


def backbone_filename(projection_id: str, construction: dict) -> str:
    """Nombre oficial estable para el backbone de una proyección."""
    if not projection_id:
        raise ValueError("projection_id es obligatorio")
    return f"backbone_{projection_id}"


def leiden_filename(backbone_name: str, configuration: dict) -> str:
    """Nombre oficial estable para Leiden derivado de un backbone."""
    projection_id = backbone_name.removeprefix("backbone_")
    if not projection_id:
        raise ValueError("backbone_name debe comenzar con 'backbone_'")
    return f"leiden_{projection_id}"


def semantic_network_filename(projection_id: str) -> str:
    """Nombre oficial estable para la meta-red de nodos semánticos."""
    if not projection_id:
        raise ValueError("projection_id es obligatorio")
    return f"semantic_network_{projection_id}"


def graphml_path(
    scope_type: str,
    scope_id: str | int | UUID | None,
    language: str,
    base_name: str,
) -> Path:
    return base_dir("graphml", scope_type, scope_id, language) / f"{base_name}.graphml"


def json_path(
    scope_type: str,
    scope_id: str | int | UUID | None,
    language: str,
    base_name: str,
) -> Path:
    return base_dir("json", scope_type, scope_id, language) / f"{base_name}.json"


def nodes_csv_path(
    scope_type: str,
    scope_id: str | int | UUID | None,
    language: str,
    base_name: str,
) -> Path:
    return base_dir("csv", scope_type, scope_id, language) / f"{base_name}_nodes.csv"


def edges_csv_path(
    scope_type: str,
    scope_id: str | int | UUID | None,
    language: str,
    base_name: str,
) -> Path:
    return base_dir("csv", scope_type, scope_id, language) / f"{base_name}_edges.csv"


def communities_csv_path(
    scope_type: str,
    scope_id: str | int | UUID | None,
    language: str,
    base_name: str,
) -> Path:
    return (
        base_dir("csv", scope_type, scope_id, language) / f"{base_name}_communities.csv"
    )


def members_csv_path(
    scope_type: str,
    scope_id: str | int | UUID | None,
    language: str,
    base_name: str,
) -> Path:
    return base_dir("csv", scope_type, scope_id, language) / f"{base_name}_members.csv"
