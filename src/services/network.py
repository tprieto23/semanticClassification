from __future__ import annotations

import json
import shutil
import tempfile
import threading
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.analysis.backbone import (
    DOCUMENT_RECURRENT_CORE_METHOD,
    DocumentRecurrentCoreConfig,
    build_document_recurrent_core,
    export_backbone_to_files,
)
from src.analysis.cooccurrence import (
    CATEGORY_ORDER,
    CooccurrenceResult,
    build_sentence_cooccurrence,
    category_pair_rows,
    load_db_mentions,
)
from src.analysis.graph_export import (
    build_metadata,
    export_cooccurrence_graph,
    write_metadata_json,
)
from src.analysis.graph_paths import (
    backbone_filename,
    communities_csv_path,
    edges_csv_path,
    graph_scope_dir,
    graphml_path,
    json_path,
    leiden_filename,
    members_csv_path,
    nodes_csv_path,
    red_plana_filename,
)
from src.analysis.leiden import (
    LeidenConfig,
    LeidenDependencyError,
    LeidenError,
    export_leiden_clustering,
    graph_file_sha256,
)
from src.analysis.projections import (
    ProjectionDefinition,
    get_projection,
    projection_manifest,
)
from src.config import settings
from src.models.canonical_entities import CanonicalEntity
from src.models.documents import Document
from src.models.entities import Entity
from src.models.sentences import Sentence
from src.services.documents import DocumentoError, DocumentoNoEncontrado

READY_STATUS = "fuzzyMatching"
_graph_locks_guard = threading.Lock()
_graph_target_locks: dict[str, threading.Lock] = {}


class NetworkDataUnavailable(DocumentoError):
    def __init__(self, detail: str):
        super().__init__(detail, 409)


class NetworkArtifactsNotFound(DocumentoError):
    def __init__(self, scope: str):
        super().__init__(
            f"No hay una red generada para {scope} con esos parámetros", 404
        )


class NetworkProjectionNotFound(DocumentoError):
    def __init__(self, projection_id: str):
        super().__init__(f"Proyección analítica no encontrada: {projection_id}", 404)


class NetworkEdgeEvidenceNotFound(DocumentoError):
    def __init__(self, source_id: str, target_id: str):
        super().__init__(
            f"No hay una arista proyectada entre {source_id} y {target_id}", 404
        )


class NetworkClusteringDependencyUnavailable(DocumentoError):
    def __init__(self):
        super().__init__(
            "Leiden no está disponible: instale las dependencias igraph y leidenalg",
            503,
        )


def _lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _graph_locks_guard:
        return _graph_target_locks.setdefault(key, threading.Lock())


def _graph_scope(
    *,
    document_id: str | None = None,
    incubator_number: int | None = None,
    language: str | None = None,
) -> tuple[str, str | int | None, str]:
    """Devuelve (scope_type, scope_id, language) para graph_paths."""
    if document_id is not None:
        return "documents", str(UUID(document_id)), language or "all"
    if incubator_number is not None:
        return "incubators", incubator_number, language or "all"
    return "corpus", None, language or "all"


def _scope_label(scope_type: str, scope_id: str | int | None, language: str) -> str:
    parts = [scope_type]
    if scope_id is not None:
        parts.append(str(scope_id))
    parts.append(language)
    return ":".join(parts)


def _replace_file(source: Path, target: Path) -> None:
    """Reemplaza ``target`` por ``source`` de forma atómica."""
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_name(f".{target.name}.previous")
    if backup.exists():
        backup.unlink()
    if target.exists():
        target.replace(backup)
    try:
        source.replace(target)
    except Exception:
        if backup.exists() and not target.exists():
            backup.replace(target)
        raise
    if backup.exists():
        backup.unlink()


def _atomic_write_files(
    writers: dict[Path, Any | None],
    lock_path: Path,
) -> None:
    """Escribe cada archivo en un temporal y lo mueve atómicamente bajo lock.

    Si un writer es ``None``, se asume que el archivo ya fue creado en el
    directorio temporal por otro writer (por ejemplo, los CSVs generados junto
    al GraphML).
    """
    temporary = Path(tempfile.mkdtemp(prefix=".graph-build-"))
    try:
        temp_files: dict[Path, Path] = {}
        for target_path, writer in writers.items():
            temp_path = temporary / target_path.name
            if writer is not None:
                writer(temp_path)
            if not temp_path.exists():
                raise FileNotFoundError(
                    f"Archivo temporal no generado: {temp_path.name}"
                )
            temp_files[target_path] = temp_path

        with _lock_for(lock_path):
            for target_path, temp_path in temp_files.items():
                _replace_file(temp_path, target_path)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _coverage(
    db: Session,
    *,
    document_id: str | None,
    incubator_number: int | None,
    language: str | None,
) -> dict:
    if document_id is not None:
        return {
            "documents_included": 1,
            "documents_total": 1,
            "excluded_by_status": {},
        }

    statement = select(Document.status, func.count(Document.id)).group_by(
        Document.status
    )
    if incubator_number is not None:
        statement = statement.where(Document.incubator_number == incubator_number)
    if language is not None:
        statement = statement.where(Document.language == language)
    status_counts = Counter(dict(db.execute(statement).all()))
    included = status_counts.pop(READY_STATUS, 0)
    return {
        "documents_included": included,
        "documents_total": included + sum(status_counts.values()),
        "excluded_by_status": dict(sorted(status_counts.items())),
    }


def _validate_document(db: Session, document_id: str) -> None:
    document = db.get(Document, UUID(document_id))
    if document is None:
        raise DocumentoNoEncontrado(document_id)
    if document.status != READY_STATUS:
        raise NetworkDataUnavailable(
            f"Documento {document_id} debe estar en estado '{READY_STATUS}' "
            f"para construir su red (estado actual: '{document.status}')"
        )


def _load_mentions(
    db: Session,
    *,
    document_id: str | None,
    incubator_number: int | None,
    language: str | None,
) -> list:
    return load_db_mentions(
        document_id,
        status=None if document_id is not None else READY_STATUS,
        incubator_number=incubator_number,
        language=language,
        db=db,
    )


def _build_red_plana_result(
    db: Session,
    *,
    document_id: str | None,
    incubator_number: int | None,
    language: str | None,
) -> tuple[CooccurrenceResult, dict]:
    if document_id is not None:
        _validate_document(db, document_id)
    mentions = _load_mentions(
        db,
        document_id=document_id,
        incubator_number=incubator_number,
        language=language,
    )
    if not mentions:
        scope_label = _scope_label(
            *_graph_scope(
                document_id=document_id,
                incubator_number=incubator_number,
                language=language,
            )
        )
        raise NetworkDataUnavailable(
            f"No hay menciones canonicalizadas disponibles para {scope_label}"
        )
    result = build_sentence_cooccurrence(mentions)
    coverage = _coverage(
        db,
        document_id=document_id,
        incubator_number=incubator_number,
        language=language,
    )
    return result, coverage


def _incubator_filter_value(scope_type: str, scope_id: str | int | None) -> Any:
    if scope_type == "incubators" and isinstance(scope_id, int):
        return scope_id
    return "all"


def _relative_output_path(path: Path) -> str:
    """Devuelve la ruta del artefacto relativa a STORAGE_GRAPHS."""
    return str(path.relative_to(settings.STORAGE_GRAPHS))


def _graph_summary_for_red_plana(
    result: CooccurrenceResult,
    minimum_weight: int,
    include_isolates: bool,
) -> dict:
    active_indexes = set(range(len(result.nodes)))
    if not include_isolates:
        active_indexes = {
            node_index
            for edge, weight in result.edge_weights.items()
            if weight >= minimum_weight
            for node_index in edge
        }
    included_edges = [
        (source, target, weight)
        for (source, target), weight in result.edge_weights.items()
        if weight >= minimum_weight
        and source in active_indexes
        and target in active_indexes
    ]
    return {
        "canonical_nodes": len(active_indexes),
        "undirected_edges": len(included_edges),
        "max_edge_weight": max(
            (weight for _, _, weight in included_edges),
            default=0,
        ),
    }


class NetworkService:
    @staticmethod
    def _projection(projection_id: str) -> ProjectionDefinition:
        projection = get_projection(projection_id)
        if projection is None:
            raise NetworkProjectionNotFound(projection_id)
        return projection

    @staticmethod
    def projection_views(projection_id: str) -> dict:
        projection = NetworkService._projection(projection_id)
        manifest = projection_manifest(projection)
        return {
            "projection": {
                key: manifest[key]
                for key in ("id", "label", "node_categories", "category_pairs")
            },
            "views": manifest["views"],
        }

    @staticmethod
    def build(
        db: Session,
        *,
        minimum_weight: int = 1,
        include_isolates: bool = True,
        document_id: str | None = None,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> dict:
        scope_type, scope_id, lang = _graph_scope(
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        result, coverage = _build_red_plana_result(
            db,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        base_name = red_plana_filename(minimum_weight, include_isolates)
        g_path = graphml_path(scope_type, scope_id, lang, base_name)
        n_path = nodes_csv_path(scope_type, scope_id, lang, base_name)
        e_path = edges_csv_path(scope_type, scope_id, lang, base_name)
        j_path = json_path(scope_type, scope_id, lang, base_name)
        lock_path = (
            settings.STORAGE_GRAPHS
            / "graphml"
            / graph_scope_dir(scope_type, scope_id, lang)
        )

        def _write_graphml(temp_path: Path) -> None:
            export_cooccurrence_graph(
                result,
                temp_path.parent,
                base_name,
                graph_metadata={
                    "scope_type": scope_type,
                    "scope_id": str(scope_id) if scope_id is not None else None,
                    "language": lang,
                    "edge_definition": "same_sentence_cooccurrence",
                    "directed": "false",
                },
                minimum_weight=minimum_weight,
                include_isolates=include_isolates,
            )

        def _write_json(temp_path: Path) -> None:
            pair_summary = category_pair_rows(
                result,
                minimum_weight=minimum_weight,
                include_isolates=include_isolates,
            )
            summary = _graph_summary_for_red_plana(
                result, minimum_weight, include_isolates
            )
            metadata = build_metadata(
                scope_type=scope_type,
                scope_id=scope_id,
                language=lang,
                base_name=base_name,
                filters={
                    "incubator_number": _incubator_filter_value(scope_type, scope_id),
                    "language": lang,
                    "minimum_weight": minimum_weight,
                    "include_isolates": include_isolates,
                },
                configuration={
                    "type": "red-plana",
                    "minimum_weight": minimum_weight,
                    "include_isolates": include_isolates,
                },
                counts={
                    "mentions": result.source_mention_count,
                    "projected_mentions": result.projected_mention_count,
                    "canonical_nodes": summary["canonical_nodes"],
                    "undirected_edges": summary["undirected_edges"],
                    "max_edge_weight": summary["max_edge_weight"],
                    "documents_included": coverage["documents_included"],
                    "documents_total": coverage["documents_total"],
                },
                outputs={
                    "graphml": _relative_output_path(g_path),
                    "nodes_csv": _relative_output_path(n_path),
                    "edges_csv": _relative_output_path(e_path),
                },
            )
            metadata["category_pair_summary"] = pair_summary
            write_metadata_json(temp_path, metadata)

        _atomic_write_files(
            {
                g_path: _write_graphml,
                n_path: None,
                e_path: None,
                j_path: _write_json,
            },
            lock_path,
        )

        with j_path.open(encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def build_projection(
        db: Session,
        projection_id: str,
        *,
        minimum_weight: int = 1,
        include_isolates: bool = True,
        document_id: str | None = None,
        incubator_number: int | None = None,
        language: str | None = None,
        construction: dict | None = None,
    ) -> dict:
        projection = NetworkService._projection(projection_id)
        scope_type, scope_id, lang = _graph_scope(
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        if document_id is not None:
            _validate_document(db, document_id)
        mentions = _load_mentions(
            db,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        if not mentions:
            raise NetworkDataUnavailable(
                "No hay menciones canonicalizadas disponibles para "
                f"{_scope_label(scope_type, scope_id, lang)}"
            )
        try:
            result = build_sentence_cooccurrence(
                mentions,
                node_categories=projection.node_categories,
                allowed_category_pairs=projection.category_pairs,
            )
        except ValueError as exc:
            raise NetworkDataUnavailable(str(exc)) from exc
        coverage = _coverage(
            db,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )

        if construction is not None:
            return NetworkService._build_projection_construction(
                projection_id,
                result,
                coverage,
                construction,
                scope_type=scope_type,
                scope_id=scope_id,
                language=lang,
                incubator_number=incubator_number,
            )

        base_name = backbone_filename(
            projection_id,
            {
                "method": "raw-threshold-v1",
                "minimum_weight": minimum_weight,
                "include_isolates": include_isolates,
            },
        )
        return NetworkService._export_projection_backbone(
            result,
            projection,
            coverage,
            base_name,
            scope_type,
            scope_id,
            lang,
            minimum_weight=minimum_weight,
            include_isolates=include_isolates,
        )

    @staticmethod
    def _export_projection_backbone(
        result: CooccurrenceResult,
        projection: ProjectionDefinition,
        coverage: dict,
        base_name: str,
        scope_type: str,
        scope_id: str | int | None,
        language: str,
        *,
        minimum_weight: int = 1,
        include_isolates: bool = True,
        config: dict | None = None,
    ) -> dict:
        g_path = graphml_path(scope_type, scope_id, language, base_name)
        n_path = nodes_csv_path(scope_type, scope_id, language, base_name)
        e_path = edges_csv_path(scope_type, scope_id, language, base_name)
        j_path = json_path(scope_type, scope_id, language, base_name)
        lock_path = (
            settings.STORAGE_GRAPHS
            / "graphml"
            / graph_scope_dir(scope_type, scope_id, language)
        )

        def _write_graphml(temp_path: Path) -> None:
            export_cooccurrence_graph(
                result,
                temp_path.parent,
                base_name,
                graph_metadata={
                    "scope_type": scope_type,
                    "scope_id": str(scope_id) if scope_id is not None else None,
                    "language": language,
                    "projection_id": projection.projection_id,
                    "edge_definition": "same_sentence_cooccurrence",
                    "directed": "false",
                },
                minimum_weight=minimum_weight,
                include_isolates=include_isolates,
            )

        def _write_json(temp_path: Path) -> None:
            pair_summary = category_pair_rows(
                result,
                minimum_weight=minimum_weight,
                include_isolates=include_isolates,
            )
            summary = _graph_summary_for_red_plana(
                result, minimum_weight, include_isolates
            )
            metadata = build_metadata(
                scope_type=scope_type,
                scope_id=scope_id,
                language=language,
                base_name=base_name,
                filters={
                    "incubator_number": _incubator_filter_value(scope_type, scope_id),
                    "language": language,
                    "minimum_weight": minimum_weight,
                    "include_isolates": include_isolates,
                },
                configuration=config
                or {
                    "type": "raw-threshold-v1",
                    "minimum_weight": minimum_weight,
                    "include_isolates": include_isolates,
                },
                counts={
                    "mentions": result.source_mention_count,
                    "projected_mentions": result.projected_mention_count,
                    "canonical_nodes": summary["canonical_nodes"],
                    "undirected_edges": summary["undirected_edges"],
                    "max_edge_weight": summary["max_edge_weight"],
                    "documents_included": coverage["documents_included"],
                    "documents_total": coverage["documents_total"],
                },
                outputs={
                    "graphml": _relative_output_path(g_path),
                    "nodes_csv": _relative_output_path(n_path),
                    "edges_csv": _relative_output_path(e_path),
                },
            )
            metadata["projection"] = {
                "id": projection.projection_id,
                "label": projection.label,
                "node_categories": list(projection.node_categories),
                "category_pairs": [
                    "--".join(pair) for pair in projection.category_pairs
                ],
            }
            metadata["category_pair_summary"] = pair_summary
            write_metadata_json(temp_path, metadata)

        _atomic_write_files(
            {
                g_path: _write_graphml,
                n_path: None,
                e_path: None,
                j_path: _write_json,
            },
            lock_path,
        )

        with j_path.open(encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _build_projection_construction(
        projection_id: str,
        result: CooccurrenceResult,
        coverage: dict,
        construction: dict,
        *,
        scope_type: str,
        scope_id: str | int | None,
        language: str,
        incubator_number: int | None,
    ) -> dict:
        method = construction.get("method")
        if method == "raw-threshold-v1":
            minimum_weight = int(construction.get("minimum_weight", 1))
            include_isolates = bool(construction.get("include_isolates", True))
            base_name = backbone_filename(
                projection_id,
                {
                    "method": "raw-threshold-v1",
                    "minimum_weight": minimum_weight,
                    "include_isolates": include_isolates,
                },
            )
            return NetworkService._export_projection_backbone(
                result,
                NetworkService._projection(projection_id),
                coverage,
                base_name,
                scope_type,
                scope_id,
                language,
                minimum_weight=minimum_weight,
                include_isolates=include_isolates,
            )

        if method == DOCUMENT_RECURRENT_CORE_METHOD:
            config = DocumentRecurrentCoreConfig(
                method=method,
                minimum_node_document_count=int(
                    construction.get("minimum_node_document_count", 2)
                ),
                edge_weighting=str(
                    construction.get("edge_weighting", "fractional-document")
                ),
                include_minor_components=bool(
                    construction.get("include_minor_components", True)
                ),
            )
            try:
                config.validate()
            except ValueError as exc:
                raise NetworkDataUnavailable(str(exc)) from exc

            build = build_document_recurrent_core(result, config)
            base_name = backbone_filename(projection_id, construction)
            g_path = graphml_path(scope_type, scope_id, language, base_name)
            n_path = nodes_csv_path(scope_type, scope_id, language, base_name)
            e_path = edges_csv_path(scope_type, scope_id, language, base_name)
            j_path = json_path(scope_type, scope_id, language, base_name)
            lock_path = (
                settings.STORAGE_GRAPHS
                / "graphml"
                / graph_scope_dir(scope_type, scope_id, language)
            )

            def _write_graphml(temp_path: Path) -> None:
                export_backbone_to_files(
                    build,
                    graphml_path=temp_path,
                    nodes_csv_path=temp_path.with_name(f"{base_name}_nodes.csv"),
                    edges_csv_path=temp_path.with_name(f"{base_name}_edges.csv"),
                    json_path=temp_path.with_name(f"{base_name}.json"),
                    metadata={
                        "projection_id": projection_id,
                        "graph": {
                            "scope_type": scope_type,
                            "scope_id": str(scope_id) if scope_id is not None else "",
                            "language": language,
                            "projection_id": projection_id,
                            "construction_method": config.method,
                            "minimum_node_document_count": config.minimum_node_document_count,
                            "edge_weighting": config.edge_weighting,
                        },
                        "scope": _scope_label(scope_type, scope_id, language),
                        "filters": {
                            "incubator_number": (
                                incubator_number
                                if incubator_number is not None
                                else "all"
                            ),
                            "language": language,
                        },
                        "configuration": {
                            "type": config.method,
                            "minimum_node_document_count": config.minimum_node_document_count,
                            "edge_weighting": config.edge_weighting,
                            "include_minor_components": config.include_minor_components,
                        },
                        "base_counts": {
                            "canonical_nodes": len(result.nodes),
                            "undirected_edges": len(result.edge_weights),
                            "sentences": len(result.sentences),
                            "edge_observations": len(result.observations),
                        },
                        "coverage": coverage,
                        "outputs": {
                            "graphml": _relative_output_path(g_path),
                            "nodes_csv": _relative_output_path(n_path),
                            "edges_csv": _relative_output_path(e_path),
                        },
                    },
                )

            _atomic_write_files(
                {
                    g_path: _write_graphml,
                    n_path: None,
                    e_path: None,
                    j_path: None,
                },
                lock_path,
            )

            with j_path.open(encoding="utf-8") as file:
                return json.load(file)

        raise NetworkDataUnavailable(f"Método de construcción no soportado: {method}")

    @staticmethod
    def cluster_projection_leiden(
        projection_id: str,
        *,
        construction: dict,
        component_scope: str = "main-component",
        view_id: str = "all",
        configuration: dict | None = None,
        force_recompute: bool = False,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> dict:
        NetworkService._projection(projection_id)
        if component_scope not in {"all-components", "main-component"}:
            raise NetworkDataUnavailable(
                "component_scope debe ser all-components o main-component"
            )
        if component_scope != "main-component" or view_id != "all":
            raise NetworkDataUnavailable(
                "La publicación simplificada usa únicamente main-component/all"
            )

        scope_type, scope_id, lang = _graph_scope(
            incubator_number=incubator_number,
            language=language,
        )
        construction_config = DocumentRecurrentCoreConfig(
            method=str(construction.get("method", "")),
            minimum_node_document_count=int(
                construction.get("minimum_node_document_count", 2)
            ),
            edge_weighting=str(
                construction.get("edge_weighting", "fractional-document")
            ),
            include_minor_components=bool(
                construction.get("include_minor_components", True)
            ),
        )
        clustering_values = configuration or {}
        clustering_config = LeidenConfig(
            method=str(clustering_values.get("method", "leiden-v1")),
            objective_function=str(
                clustering_values.get("objective_function", "modularity")
            ),
            resolution=float(clustering_values.get("resolution", 1.0)),
            seed=int(clustering_values.get("seed", 42)),
            iterations=int(clustering_values.get("iterations", -1)),
            weight_attribute=str(clustering_values.get("weight_attribute", "weight")),
        )
        try:
            construction_config.validate()
            clustering_config.validate()
        except (ValueError, LeidenError) as exc:
            raise NetworkDataUnavailable(str(exc)) from exc

        backbone_name = backbone_filename(projection_id, construction)
        leiden_name = leiden_filename(backbone_name, clustering_values)
        source_graphml = graphml_path(scope_type, scope_id, lang, backbone_name)
        g_path = graphml_path(scope_type, scope_id, lang, leiden_name)
        j_path = json_path(scope_type, scope_id, lang, leiden_name)
        c_path = communities_csv_path(scope_type, scope_id, lang, leiden_name)
        m_path = members_csv_path(scope_type, scope_id, lang, leiden_name)
        lock_path = (
            settings.STORAGE_GRAPHS
            / "graphml"
            / graph_scope_dir(scope_type, scope_id, lang)
        )

        with _lock_for(lock_path):
            if not source_graphml.is_file():
                raise NetworkArtifactsNotFound(
                    f"{projection_id}/{construction}/{component_scope}/{view_id}"
                )
            source_hash = graph_file_sha256(source_graphml)
            if not force_recompute and j_path.is_file():
                try:
                    with j_path.open(encoding="utf-8") as file:
                        cached = json.load(file)
                except (OSError, json.JSONDecodeError):
                    cached = None
                if (
                    isinstance(cached, dict)
                    and cached.get("source", {}).get("graphml_sha256") == source_hash
                    and cached.get("configuration") == clustering_config.__dict__
                ):
                    cached["cached"] = True
                    return cached

            temporary = Path(tempfile.mkdtemp(prefix=".leiden-build-"))
            try:
                try:
                    payload = export_leiden_clustering(
                        source_graphml,
                        temporary,
                        config=clustering_config,
                        base_name=leiden_name,
                    )
                except LeidenDependencyError as exc:
                    raise NetworkClusteringDependencyUnavailable() from exc
                except LeidenError as exc:
                    raise NetworkDataUnavailable(str(exc)) from exc

                metadata = build_metadata(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    language=lang,
                    base_name=leiden_name,
                    filters={
                        "incubator_number": (
                            incubator_number if incubator_number is not None else "all"
                        ),
                        "language": lang,
                        "component_scope": component_scope,
                        "view_id": view_id,
                    },
                    configuration=clustering_config.__dict__,
                    counts=payload["counts"],
                    outputs={
                        "graphml": _relative_output_path(g_path),
                        "communities_csv": _relative_output_path(c_path),
                        "members_csv": _relative_output_path(m_path),
                    },
                    graph_hash=source_hash,
                    metrics={
                        "modularity": payload["modularity"],
                        "objective_quality": payload["objective_quality"],
                    },
                )
                metadata["projection_id"] = projection_id
                metadata["source"] = payload["source"]
                metadata["status"] = payload["status"]
                metadata["cached"] = False
                write_metadata_json(temporary / f"{leiden_name}.json", metadata)

                _replace_file(
                    temporary / payload["outputs"]["clustered_graphml"], g_path
                )
                _replace_file(temporary / payload["outputs"]["communities_csv"], c_path)
                _replace_file(
                    temporary / payload["outputs"]["community_members_csv"], m_path
                )
                _replace_file(temporary / f"{leiden_name}.json", j_path)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)

        with j_path.open(encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def latest(
        *,
        minimum_weight: int = 1,
        include_isolates: bool = True,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> dict:
        scope_type, scope_id, lang = _graph_scope(
            incubator_number=incubator_number,
            language=language,
        )
        base_name = red_plana_filename(minimum_weight, include_isolates)
        j_path = json_path(scope_type, scope_id, lang, base_name)
        if not j_path.exists():
            raise NetworkArtifactsNotFound(_scope_label(scope_type, scope_id, lang))
        with j_path.open(encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise NetworkArtifactsNotFound(_scope_label(scope_type, scope_id, lang))
        return payload

    @staticmethod
    def latest_projection(
        projection_id: str,
        *,
        minimum_weight: int = 1,
        include_isolates: bool = True,
        document_id: str | None = None,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> dict:
        NetworkService._projection(projection_id)
        scope_type, scope_id, lang = _graph_scope(
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        base_name = backbone_filename(
            projection_id,
            {
                "method": "raw-threshold-v1",
                "minimum_weight": minimum_weight,
                "include_isolates": include_isolates,
            },
        )
        j_path = json_path(scope_type, scope_id, lang, base_name)
        if not j_path.exists():
            raise NetworkArtifactsNotFound(
                f"{projection_id}/{_scope_label(scope_type, scope_id, lang)}"
            )
        with j_path.open(encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise NetworkArtifactsNotFound(
                f"{projection_id}/{_scope_label(scope_type, scope_id, lang)}"
            )
        return payload

    @staticmethod
    def edge_evidence(
        db: Session,
        projection_id: str,
        source_id: str,
        target_id: str,
        *,
        minimum_weight: int = 1,
        include_isolates: bool = True,
        document_id: str | None = None,
        incubator_number: int | None = None,
        language: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        projection = NetworkService._projection(projection_id)
        scope_type, scope_id, lang = _graph_scope(
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        base_name = backbone_filename(
            projection_id,
            {
                "method": "raw-threshold-v1",
                "minimum_weight": minimum_weight,
                "include_isolates": include_isolates,
            },
        )
        j_path = json_path(scope_type, scope_id, lang, base_name)
        if not j_path.exists():
            raise NetworkArtifactsNotFound(
                f"{projection_id}/{_scope_label(scope_type, scope_id, lang)}"
            )

        source_uuid = UUID(source_id)
        target_uuid = UUID(target_id)
        projected_categories = set(projection.node_categories)

        def scoped_entity_sentences(canonical_id: UUID):
            statement = (
                select(Entity.document_id, Entity.sentence_id)
                .join(Document, Document.id == Entity.document_id)
                .where(Entity.canonical_id == canonical_id)
            )
            if document_id is not None:
                statement = statement.where(Document.id == UUID(document_id))
            else:
                statement = statement.where(Document.status == READY_STATUS)
            if incubator_number is not None:
                statement = statement.where(
                    Document.incubator_number == incubator_number
                )
            if language is not None:
                statement = statement.where(Document.language == language)
            return statement

        sentence_subquery = (
            scoped_entity_sentences(source_uuid)
            .intersect(scoped_entity_sentences(target_uuid))
            .subquery("common_sentences")
        )

        statement = (
            select(
                Sentence.document_id,
                Sentence.sentence_id,
                Sentence.text.label("context"),
                Entity.canonical_id,
                CanonicalEntity.canonical_name,
                Entity.category,
                Entity.text.label("mention_text"),
                Entity.ambiguity,
            )
            .join(
                sentence_subquery,
                (Sentence.document_id == sentence_subquery.c.document_id)
                & (Sentence.sentence_id == sentence_subquery.c.sentence_id),
            )
            .join(
                Entity,
                (Entity.document_id == Sentence.document_id)
                & (Entity.sentence_id == Sentence.sentence_id),
            )
            .join(CanonicalEntity, CanonicalEntity.id == Entity.canonical_id)
            .order_by(Sentence.document_id, Sentence.sentence_id, Entity.position_start)
        )

        rows = db.execute(statement).all()

        sentences_map: dict[tuple[str, str], dict] = {}
        for row in rows:
            key = (str(row.document_id), row.sentence_id)
            sentence = sentences_map.setdefault(
                key,
                {
                    "document_id": str(row.document_id),
                    "sentence_id": row.sentence_id,
                    "context": row.context,
                    "projected_entities": [],
                    "context_entities": [],
                },
            )
            entity = {
                "canonical_id": str(row.canonical_id),
                "canonical_name": row.canonical_name,
                "category": row.category,
                "is_projected": row.category in projected_categories,
                "mention_text": row.mention_text,
                "ambiguity": row.ambiguity,
            }
            if entity not in sentence["context_entities"]:
                sentence["context_entities"].append(entity)
            if entity["is_projected"] and entity not in sentence["projected_entities"]:
                sentence["projected_entities"].append(entity)

        items = list(sentences_map.values())
        if len(items) < minimum_weight:
            raise NetworkEdgeEvidenceNotFound(source_id, target_id)

        return {
            "projection_id": projection_id,
            "scope": _scope_label(scope_type, scope_id, lang),
            "edge": {
                "source_canonical_id": source_id,
                "target_canonical_id": target_id,
            },
            "total": len(items),
            "offset": offset,
            "limit": limit,
            "items": items[offset : offset + limit],
        }

    @staticmethod
    def with_public_urls(payload: dict, base_url: str) -> dict:
        prefix = f"{base_url.rstrip('/')}/files/graphs"

        def rewrite(value, *, outputs: bool = False):
            if isinstance(value, dict):
                return {
                    key: rewrite(item, outputs=outputs or key == "outputs")
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [rewrite(item) for item in value]
            if outputs and isinstance(value, str):
                return f"{prefix}/{value}"
            return value

        return rewrite(payload)
