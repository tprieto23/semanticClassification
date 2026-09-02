from __future__ import annotations

import csv
import json
import shutil
import tempfile
import threading
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.analysis.backbone import (
    DOCUMENT_RECURRENT_CORE_METHOD,
    DocumentRecurrentCoreConfig,
    export_document_recurrent_core,
)
from src.analysis.cooccurrence import (
    CATEGORY_ORDER,
    build_sentence_cooccurrence,
    category_pair_rows,
    export_result,
    load_db_mentions,
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
    ProjectionView,
    get_projection,
    projection_manifest,
)
from src.config import settings
from src.models.documents import Document
from src.services.documents import DocumentoError, DocumentoNoEncontrado

READY_STATUS = "fuzzyMatching"
_locks_guard = threading.Lock()
_target_locks: dict[str, threading.Lock] = {}


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


class NetworkViewNotFound(DocumentoError):
    def __init__(self, projection_id: str, view_id: str):
        super().__init__(
            f"Vista '{view_id}' no encontrada en la proyección {projection_id}", 404
        )


class NetworkClusteringDependencyUnavailable(DocumentoError):
    def __init__(self):
        super().__init__(
            "Leiden no está disponible: instale las dependencias igraph y leidenalg",
            503,
        )


def _lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _locks_guard:
        return _target_locks.setdefault(key, threading.Lock())


class NetworkService:
    @staticmethod
    def _scope(
        *,
        document_id: str | None = None,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> tuple[str, Path]:
        if document_id is not None:
            normalized = str(UUID(document_id))
            return f"document:{normalized}", Path("documents") / normalized
        if incubator_number is not None:
            scope = f"incubator:{incubator_number}"
            path = Path(f"incubator-{incubator_number}")
            if language is not None:
                return f"{scope},language:{language}", path / f"language-{language}"
            return scope, path
        if language is not None:
            return f"language:{language}", Path("corpus") / f"language-{language}"
        return "corpus", Path("corpus")

    @staticmethod
    def _target_dir(
        *,
        minimum_weight: int,
        include_isolates: bool,
        document_id: str | None = None,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> tuple[str, Path]:
        scope, scope_path = NetworkService._scope(
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        isolate_slug = "isolates" if include_isolates else "no-isolates"
        target = (
            settings.STORAGE_NETWORK / scope_path / f"w{minimum_weight}-{isolate_slug}"
        )
        return scope, target

    @staticmethod
    def _projection(projection_id: str) -> ProjectionDefinition:
        projection = get_projection(projection_id)
        if projection is None:
            raise NetworkProjectionNotFound(projection_id)
        return projection

    @staticmethod
    def _projection_target_dir(
        projection_id: str,
        *,
        minimum_weight: int,
        include_isolates: bool,
        document_id: str | None = None,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> tuple[str, Path]:
        NetworkService._projection(projection_id)
        scope, scope_path = NetworkService._scope(
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        isolate_slug = "isolates" if include_isolates else "no-isolates"
        target = (
            settings.STORAGE_NETWORK
            / scope_path
            / "projections"
            / projection_id
            / f"w{minimum_weight}-{isolate_slug}"
        )
        return scope, target

    @staticmethod
    def _construction_target_dir(
        projection_id: str,
        config: DocumentRecurrentCoreConfig,
        *,
        document_id: str | None = None,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> tuple[str, Path]:
        NetworkService._projection(projection_id)
        scope, scope_path = NetworkService._scope(
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        component_slug = (
            "with-minor-components"
            if config.include_minor_components
            else "main-component-only"
        )
        target = (
            settings.STORAGE_NETWORK
            / scope_path
            / "projections"
            / projection_id
            / "constructions"
            / config.method
            / f"node-documents-{config.minimum_node_document_count}"
            / f"edge-weight-{config.edge_weighting}"
            / component_slug
        )
        return scope, target

    @staticmethod
    def _leiden_target_dir(source_view_dir: Path, config: LeidenConfig) -> Path:
        resolution_slug = format(config.resolution, ".12g")
        iterations_slug = (
            "converge" if config.iterations == -1 else str(config.iterations)
        )
        return (
            source_view_dir
            / "clusterings"
            / config.method
            / f"objective-{config.objective_function}"
            / f"resolution-{resolution_slug}"
            / f"seed-{config.seed}"
            / f"iterations-{iterations_slug}"
            / f"weight-{config.weight_attribute}"
        )

    @staticmethod
    def _qualify_output_paths(payload: dict, relative_dir: Path) -> dict:
        """Prefija únicamente valores contenidos en objetos ``outputs``."""

        def qualify(value, *, outputs: bool = False):
            if isinstance(value, dict):
                return {
                    key: qualify(item, outputs=outputs or key == "outputs")
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [qualify(item, outputs=outputs) for item in value]
            if outputs and isinstance(value, str):
                return (relative_dir / value).as_posix()
            return value

        return qualify(payload)

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

    @staticmethod
    def _validate_document(db: Session, document_id: str) -> None:
        document = db.get(Document, UUID(document_id))
        if document is None:
            raise DocumentoNoEncontrado(document_id)
        if document.status != READY_STATUS:
            raise NetworkDataUnavailable(
                f"Documento {document_id} debe estar en estado '{READY_STATUS}' "
                f"para construir su red (estado actual: '{document.status}')"
            )

    @staticmethod
    def _replace_directory(source: Path, target: Path) -> None:
        backup = target.with_name(f".{target.name}.previous")
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            target.replace(backup)
        try:
            source.replace(target)
        except Exception:
            if backup.exists() and not target.exists():
                backup.replace(target)
            raise
        if backup.exists():
            shutil.rmtree(backup)

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
        # Matplotlib/NetworkX son dependencias del análisis, no del arranque de la API.
        # La importación diferida mantiene disponibles los demás endpoints aunque el
        # entorno de despliegue todavía no haya instalado el extra de visualización.
        from src.analysis.network_visualization import generate_visualizations

        if document_id is not None:
            NetworkService._validate_document(db, document_id)

        scope, target = NetworkService._target_dir(
            minimum_weight=minimum_weight,
            include_isolates=include_isolates,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        coverage = NetworkService._coverage(
            db,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        mentions = load_db_mentions(
            document_id,
            status=None if document_id is not None else READY_STATUS,
            incubator_number=incubator_number,
            language=language,
            db=db,
        )
        if not mentions:
            raise NetworkDataUnavailable(
                f"No hay menciones canonicalizadas disponibles para {scope}"
            )

        result = build_sentence_cooccurrence(mentions)
        target.parent.mkdir(parents=True, exist_ok=True)
        with _lock_for(target):
            temporary = Path(
                tempfile.mkdtemp(prefix=".network-build-", dir=target.parent)
            )
            try:
                analysis_summary = export_result(
                    result,
                    temporary,
                    scope=scope,
                    document_id=document_id,
                    mention_count=len(mentions),
                )
                visual_summary = generate_visualizations(
                    temporary,
                    temporary,
                    minimum_weight=minimum_weight,
                    include_isolates=include_isolates,
                )
                relative_dir = target.relative_to(settings.STORAGE_NETWORK)
                output_names = {
                    **visual_summary["outputs"],
                    "analysis_summary_json": "summary.json",
                    "analysis_nodes_csv": "nodes.csv",
                    "analysis_edges_csv": "edges.csv",
                    "sentences_csv": "sentences.csv",
                    "sentence_entities_csv": "sentence_entities.csv",
                    "edge_observations_csv": "edge_observations.csv",
                    "category_pair_summary_csv": "category_pair_summary.csv",
                    "cooccurrence_matrix": "cooccurrence_adjacency.mtx",
                    "incidence_matrix": "sentence_node_incidence.mtx",
                }
                outputs = {
                    name: (relative_dir / filename).as_posix()
                    for name, filename in output_names.items()
                }
                pair_summary = category_pair_rows(
                    result,
                    minimum_weight,
                    include_isolates=include_isolates,
                )
                response = {
                    "generated_at": analysis_summary["generated_at"],
                    "scope": scope,
                    "filters": {
                        "incubator_number": incubator_number or "all",
                        "language": language or "all",
                    },
                    "minimum_weight": minimum_weight,
                    "includes_isolates": include_isolates,
                    "coverage": coverage,
                    "counts": {
                        "mentions": len(mentions),
                        "canonical_nodes": visual_summary["nodes"],
                        "sentences": analysis_summary["counts"]["sentences"],
                        "undirected_edges": visual_summary["edges"],
                        "edge_observations": sum(
                            1
                            for observation in result.observations
                            if result.edge_weights[
                                (observation.source_index, observation.target_index)
                            ]
                            >= minimum_weight
                        ),
                        "max_edge_weight": max(
                            (
                                weight
                                for weight in result.edge_weights.values()
                                if weight >= minimum_weight
                            ),
                            default=0,
                        ),
                        "components": visual_summary["components"],
                    },
                    "nodes_by_category": {
                        category: visual_summary["nodes_by_category"][category]
                        for category in CATEGORY_ORDER
                    },
                    "category_pair_summary": pair_summary,
                    "top_nodes_by_strength": visual_summary["top_nodes_by_strength"],
                    "outputs": outputs,
                }
                with (temporary / "api_response.json").open(
                    "w", encoding="utf-8"
                ) as file:
                    json.dump(response, file, ensure_ascii=False, indent=2)
                    file.write("\n")
                NetworkService._replace_directory(temporary, target)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        return response

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
        """Construye una proyección maestra y todas sus vistas registradas."""

        if construction is not None:
            method = construction.get("method")
            if method == "raw-threshold-v1":
                minimum_weight = int(construction.get("minimum_weight", 1))
                include_isolates = bool(construction.get("include_isolates", True))
            elif method == DOCUMENT_RECURRENT_CORE_METHOD:
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
                return NetworkService._build_projection_construction(
                    db,
                    projection_id,
                    config=config,
                    document_id=document_id,
                    incubator_number=incubator_number,
                    language=language,
                )
            else:
                raise NetworkDataUnavailable(
                    f"Método de construcción no soportado: {method}"
                )

        from src.analysis.network_visualization import generate_visualizations

        projection = NetworkService._projection(projection_id)
        if document_id is not None:
            NetworkService._validate_document(db, document_id)

        scope, target = NetworkService._projection_target_dir(
            projection_id,
            minimum_weight=minimum_weight,
            include_isolates=include_isolates,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        coverage = NetworkService._coverage(
            db,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        mentions = load_db_mentions(
            document_id,
            status=None if document_id is not None else READY_STATUS,
            incubator_number=incubator_number,
            language=language,
            db=db,
        )
        if not mentions:
            raise NetworkDataUnavailable(
                f"No hay menciones canonicalizadas disponibles para {scope}"
            )
        try:
            result = build_sentence_cooccurrence(
                mentions,
                node_categories=projection.node_categories,
                allowed_category_pairs=projection.category_pairs,
            )
        except ValueError as exc:
            raise NetworkDataUnavailable(str(exc)) from exc

        target.parent.mkdir(parents=True, exist_ok=True)
        with _lock_for(target):
            temporary = Path(
                tempfile.mkdtemp(prefix=".projection-build-", dir=target.parent)
            )
            try:
                evidence_dir = temporary / "evidence"
                analysis_summary = export_result(
                    result,
                    evidence_dir,
                    scope=scope,
                    document_id=document_id,
                    mention_count=len(mentions),
                )

                relative_dir = target.relative_to(settings.STORAGE_NETWORK)
                view_payloads: dict[str, dict] = {}
                view_summaries: dict[str, dict] = {}
                for view in projection.views:
                    view_dir = temporary / "views" / view.view_id
                    visual_summary = generate_visualizations(
                        evidence_dir,
                        view_dir,
                        minimum_weight=minimum_weight,
                        include_isolates=include_isolates,
                        node_categories=view.node_categories,
                        allowed_category_pairs=view.category_pair_labels,
                    )
                    view_outputs = {
                        name: (
                            relative_dir / "views" / view.view_id / filename
                        ).as_posix()
                        for name, filename in visual_summary["outputs"].items()
                    }
                    pair_set = set(view.category_pairs)
                    qualifying_observations = [
                        observation
                        for observation in result.observations
                        if observation.category_pair in pair_set
                        and result.edge_weights[
                            (observation.source_index, observation.target_index)
                        ]
                        >= minimum_weight
                    ]
                    view_definition = {
                        "id": view.view_id,
                        "label": view.label,
                        "node_categories": list(view.node_categories),
                        "category_pairs": list(view.category_pair_labels),
                    }
                    view_payloads[view.view_id] = {
                        **view_definition,
                        "counts": {
                            "canonical_nodes": visual_summary["nodes"],
                            "undirected_edges": visual_summary["edges"],
                            "components": visual_summary["components"],
                            "edge_observations": len(qualifying_observations),
                            "max_edge_weight": max(
                                (
                                    result.edge_weights[
                                        (
                                            observation.source_index,
                                            observation.target_index,
                                        )
                                    ]
                                    for observation in qualifying_observations
                                ),
                                default=0,
                            ),
                        },
                        "nodes_by_category": visual_summary["nodes_by_category"],
                        "edges_by_category_pair": visual_summary[
                            "edges_by_category_pair"
                        ],
                        "outputs": view_outputs,
                    }
                    view_summaries[view.view_id] = visual_summary

                all_view = next(
                    view for view in projection.views if view.view_id == "all"
                )
                all_summary = view_summaries[all_view.view_id]
                all_payload = view_payloads[all_view.view_id]
                qualifying_edge_keys = {
                    edge
                    for edge, weight in result.edge_weights.items()
                    if weight >= minimum_weight
                }
                qualifying_observations = [
                    observation
                    for observation in result.observations
                    if (
                        observation.source_index,
                        observation.target_index,
                    )
                    in qualifying_edge_keys
                ]
                projection_data = projection_manifest(projection)
                projection_definition = {
                    key: projection_data[key]
                    for key in (
                        "id",
                        "label",
                        "node_categories",
                        "category_pairs",
                    )
                }
                evidence_outputs = {
                    "projection_manifest_json": (
                        relative_dir / "projection_manifest.json"
                    ).as_posix(),
                    "analysis_summary_json": (
                        relative_dir / "evidence" / "summary.json"
                    ).as_posix(),
                    "master_nodes_csv": (
                        relative_dir / "evidence" / "nodes.csv"
                    ).as_posix(),
                    "master_edges_csv": (
                        relative_dir / "evidence" / "edges.csv"
                    ).as_posix(),
                    "sentences_csv": (
                        relative_dir / "evidence" / "sentences.csv"
                    ).as_posix(),
                    "sentence_entities_csv": (
                        relative_dir / "evidence" / "sentence_entities.csv"
                    ).as_posix(),
                    "edge_observations_csv": (
                        relative_dir / "evidence" / "edge_observations.csv"
                    ).as_posix(),
                    "category_pair_summary_csv": (
                        relative_dir / "evidence" / "category_pair_summary.csv"
                    ).as_posix(),
                    "cooccurrence_matrix": (
                        relative_dir / "evidence" / "cooccurrence_adjacency.mtx"
                    ).as_posix(),
                    "incidence_matrix": (
                        relative_dir / "evidence" / "sentence_node_incidence.mtx"
                    ).as_posix(),
                }
                response = {
                    "generated_at": analysis_summary["generated_at"],
                    "scope": scope,
                    "projection": projection_definition,
                    "view": {
                        "id": all_view.view_id,
                        "label": all_view.label,
                        "node_categories": list(all_view.node_categories),
                        "category_pairs": list(all_view.category_pair_labels),
                    },
                    "filters": {
                        "incubator_number": incubator_number or "all",
                        "language": language or "all",
                    },
                    "minimum_weight": minimum_weight,
                    "includes_isolates": include_isolates,
                    "coverage": coverage,
                    "counts": {
                        "mentions": result.projected_mention_count,
                        "source_mentions": result.source_mention_count,
                        "projected_mentions": result.projected_mention_count,
                        "context_mentions_in_projected_sentences": analysis_summary[
                            "counts"
                        ]["context_mentions_in_projected_sentences"],
                        "canonical_nodes": all_summary["nodes"],
                        "sentences": analysis_summary["counts"]["sentences"],
                        "sentences_with_edges": len(
                            {
                                observation.sentence_row
                                for observation in qualifying_observations
                            }
                        ),
                        "sentence_entity_presences": analysis_summary["counts"][
                            "sentence_entity_presences"
                        ],
                        "undirected_edges": all_summary["edges"],
                        "edge_observations": len(qualifying_observations),
                        "max_edge_weight": max(
                            (
                                weight
                                for weight in result.edge_weights.values()
                                if weight >= minimum_weight
                            ),
                            default=0,
                        ),
                        "components": all_summary["components"],
                    },
                    "nodes_by_category": all_summary["nodes_by_category"],
                    "category_pair_summary": category_pair_rows(
                        result,
                        minimum_weight,
                        include_isolates=include_isolates,
                    ),
                    "top_nodes_by_strength": all_summary["top_nodes_by_strength"],
                    "outputs": {**all_payload["outputs"], **evidence_outputs},
                    "views": view_payloads,
                }
                manifest_payload = {
                    "generated_at": analysis_summary["generated_at"],
                    "scope": scope,
                    "projection": projection_data,
                    "filters": response["filters"],
                    "minimum_weight": minimum_weight,
                    "includes_isolates": include_isolates,
                    "evidence_directory": "evidence",
                    "views_directory": "views",
                }
                with (temporary / "projection_manifest.json").open(
                    "w", encoding="utf-8"
                ) as file:
                    json.dump(manifest_payload, file, ensure_ascii=False, indent=2)
                    file.write("\n")
                with (temporary / "api_response.json").open(
                    "w", encoding="utf-8"
                ) as file:
                    json.dump(response, file, ensure_ascii=False, indent=2)
                    file.write("\n")
                NetworkService._replace_directory(temporary, target)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        return response

    @staticmethod
    def _build_projection_construction(
        db: Session,
        projection_id: str,
        *,
        config: DocumentRecurrentCoreConfig,
        document_id: str | None = None,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> dict:
        """Construye evidencia W1 y deriva un backbone parametrizado."""

        try:
            config.validate()
        except ValueError as exc:
            raise NetworkDataUnavailable(str(exc)) from exc
        projection = NetworkService._projection(projection_id)
        if document_id is not None:
            NetworkService._validate_document(db, document_id)
        scope, target = NetworkService._construction_target_dir(
            projection_id,
            config,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        coverage = NetworkService._coverage(
            db,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        mentions = load_db_mentions(
            document_id,
            status=None if document_id is not None else READY_STATUS,
            incubator_number=incubator_number,
            language=language,
            db=db,
        )
        if not mentions:
            raise NetworkDataUnavailable(
                f"No hay menciones canonicalizadas disponibles para {scope}"
            )
        try:
            result = build_sentence_cooccurrence(
                mentions,
                node_categories=projection.node_categories,
                allowed_category_pairs=projection.category_pairs,
            )
        except ValueError as exc:
            raise NetworkDataUnavailable(str(exc)) from exc

        target.parent.mkdir(parents=True, exist_ok=True)
        with _lock_for(target):
            temporary = Path(
                tempfile.mkdtemp(prefix=".construction-build-", dir=target.parent)
            )
            try:
                evidence_dir = temporary / "evidence"
                export_result(
                    result,
                    evidence_dir,
                    scope=scope,
                    document_id=document_id,
                    mention_count=len(mentions),
                )
                payload = export_document_recurrent_core(
                    result,
                    temporary,
                    scope=scope,
                    projection=projection,
                    config=config,
                    filters={
                        "incubator_number": incubator_number or "all",
                        "language": language or "all",
                    },
                )
                payload["coverage"] = coverage
                payload["outputs"].update(
                    {
                        "base_analysis_summary_json": "evidence/summary.json",
                        "base_nodes_csv": "evidence/nodes.csv",
                        "base_edges_csv": "evidence/edges.csv",
                        "sentences_csv": "evidence/sentences.csv",
                        "sentence_entities_csv": "evidence/sentence_entities.csv",
                        "edge_observations_csv": "evidence/edge_observations.csv",
                        "category_pair_summary_csv": (
                            "evidence/category_pair_summary.csv"
                        ),
                    }
                )
                relative_dir = target.relative_to(settings.STORAGE_NETWORK)
                response = NetworkService._qualify_output_paths(payload, relative_dir)
                with (temporary / "api_response.json").open(
                    "w", encoding="utf-8"
                ) as file:
                    json.dump(response, file, ensure_ascii=False, indent=2)
                    file.write("\n")
                NetworkService._replace_directory(temporary, target)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        return response

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
        """Calcula Leiden sobre una vista existente sin reconstruir la red."""

        projection = NetworkService._projection(projection_id)
        view = next(
            (
                candidate
                for candidate in projection.views
                if candidate.view_id == view_id
            ),
            None,
        )
        if view is None:
            raise NetworkViewNotFound(projection_id, view_id)
        if component_scope not in {"all-components", "main-component"}:
            raise NetworkDataUnavailable(
                "component_scope debe ser all-components o main-component"
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

        scope, construction_target = NetworkService._construction_target_dir(
            projection_id,
            construction_config,
            incubator_number=incubator_number,
            language=language,
        )
        source_view_dir = construction_target / "views" / component_scope / view.view_id
        source_graphml = source_view_dir / "network.graphml"
        clustering_target = NetworkService._leiden_target_dir(
            source_view_dir, clustering_config
        )
        construction_target.parent.mkdir(parents=True, exist_ok=True)

        # El mismo bloqueo que usa la construcción impide leer el GraphML mientras
        # su directorio raíz está siendo reemplazado atómicamente.
        with _lock_for(construction_target):
            if not source_graphml.is_file():
                raise NetworkArtifactsNotFound(
                    f"{scope},projection:{projection_id},"
                    f"construction:{construction_config.method},"
                    f"component_scope:{component_scope},view:{view.view_id}"
                )
            source_hash = graph_file_sha256(source_graphml)
            cached_path = clustering_target / "api_response.json"
            if not force_recompute and cached_path.is_file():
                try:
                    with cached_path.open(encoding="utf-8") as file:
                        cached = json.load(file)
                except (OSError, json.JSONDecodeError):
                    cached = None
                if (
                    isinstance(cached, dict)
                    and cached.get("source", {}).get("graphml_sha256") == source_hash
                    and cached.get("configuration") == asdict(clustering_config)
                ):
                    cached["cached"] = True
                    return cached

            clustering_target.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(
                tempfile.mkdtemp(prefix=".leiden-build-", dir=clustering_target.parent)
            )
            try:
                try:
                    payload = export_leiden_clustering(
                        source_graphml,
                        temporary,
                        config=clustering_config,
                    )
                except LeidenDependencyError as exc:
                    raise NetworkClusteringDependencyUnavailable() from exc
                except LeidenError as exc:
                    raise NetworkDataUnavailable(str(exc)) from exc

                filters = {
                    "incubator_number": incubator_number or "all",
                    "language": language or "all",
                }
                view_definition = {
                    "id": view.view_id,
                    "label": view.label,
                    "node_categories": list(view.node_categories),
                    "category_pairs": list(view.category_pair_labels),
                }
                source_relative = source_graphml.relative_to(
                    settings.STORAGE_NETWORK
                ).as_posix()
                clustering_relative = clustering_target.relative_to(
                    settings.STORAGE_NETWORK
                )
                local_outputs = dict(payload["outputs"])
                local_outputs["api_response_json"] = "api_response.json"
                response = {
                    **payload,
                    "scope": scope,
                    "filters": filters,
                    "projection_id": projection_id,
                    "construction": asdict(construction_config),
                    "source": {
                        **payload["source"],
                        "component_scope": component_scope,
                        "view": view_definition,
                        "outputs": {"graphml": source_relative},
                    },
                    "outputs": {
                        name: (clustering_relative / filename).as_posix()
                        for name, filename in local_outputs.items()
                    },
                }
                # El resumen persistido usa rutas relativas al mount público; la
                # capa HTTP será la única que les anteponga host y /files/networks.
                with (temporary / "clustering_summary.json").open(
                    "w", encoding="utf-8"
                ) as file:
                    json.dump(response, file, ensure_ascii=False, indent=2)
                    file.write("\n")
                with (temporary / "api_response.json").open(
                    "w", encoding="utf-8"
                ) as file:
                    json.dump(response, file, ensure_ascii=False, indent=2)
                    file.write("\n")
                NetworkService._replace_directory(temporary, clustering_target)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        return response

    @staticmethod
    def latest(
        *,
        minimum_weight: int = 1,
        include_isolates: bool = True,
        incubator_number: int | None = None,
        language: str | None = None,
    ) -> dict:
        scope, target = NetworkService._target_dir(
            minimum_weight=minimum_weight,
            include_isolates=include_isolates,
            incubator_number=incubator_number,
            language=language,
        )
        path = target / "api_response.json"
        if not path.exists():
            raise NetworkArtifactsNotFound(scope)
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise NetworkArtifactsNotFound(scope)
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
        scope, target = NetworkService._projection_target_dir(
            projection_id,
            minimum_weight=minimum_weight,
            include_isolates=include_isolates,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        path = target / "api_response.json"
        if not path.exists():
            raise NetworkArtifactsNotFound(f"{scope},projection:{projection_id}")
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise NetworkArtifactsNotFound(f"{scope},projection:{projection_id}")
        return payload

    @staticmethod
    def edge_evidence(
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
        scope, target = NetworkService._projection_target_dir(
            projection_id,
            minimum_weight=minimum_weight,
            include_isolates=include_isolates,
            document_id=document_id,
            incubator_number=incubator_number,
            language=language,
        )
        evidence_dir = target / "evidence"
        if not (target / "api_response.json").exists():
            raise NetworkArtifactsNotFound(f"{scope},projection:{projection_id}")

        def read_rows(filename: str) -> list[dict[str, str]]:
            path = evidence_dir / filename
            if not path.exists():
                raise NetworkArtifactsNotFound(f"{scope},projection:{projection_id}")
            with path.open(encoding="utf-8", newline="") as file:
                return list(csv.DictReader(file))

        edge_row = next(
            (
                row
                for row in read_rows("edges.csv")
                if {
                    row.get("source_canonical_id", ""),
                    row.get("target_canonical_id", ""),
                }
                == {source_id, target_id}
                and int(row.get("sentence_count") or 0) >= minimum_weight
            ),
            None,
        )
        if edge_row is None:
            raise NetworkEdgeEvidenceNotFound(source_id, target_id)

        observations = [
            row
            for row in read_rows("edge_observations.csv")
            if {
                row.get("source_canonical_id", ""),
                row.get("target_canonical_id", ""),
            }
            == {source_id, target_id}
        ]
        sentences = {
            (row["document_id"], row["sentence_id"]): row
            for row in read_rows("sentences.csv")
        }
        entities_by_sentence: dict[tuple[str, str], list[dict]] = {}
        for row in read_rows("sentence_entities.csv"):
            key = (row["document_id"], row["sentence_id"])
            entities_by_sentence.setdefault(key, []).append(
                {
                    "canonical_id": row["canonical_id"],
                    "canonical_name": row["canonical_name"],
                    "category": row["category"],
                    "is_projected": row["is_projected"].casefold() == "true",
                    "mention_count": int(row["mention_count"]),
                    "texts": [
                        item for item in row.get("texts", "").split(" | ") if item
                    ],
                    "ambiguities": [
                        item for item in row.get("ambiguities", "").split(" | ") if item
                    ],
                }
            )

        items = []
        for observation in observations[offset : offset + limit]:
            key = (observation["document_id"], observation["sentence_id"])
            sentence = sentences.get(key, {})
            context_entities = entities_by_sentence.get(key, [])
            items.append(
                {
                    "document_id": observation["document_id"],
                    "sentence_id": observation["sentence_id"],
                    "context": sentence.get("context")
                    or observation.get("context", ""),
                    "pair_context": observation.get("pair_context", ""),
                    "projected_entities": [
                        entity for entity in context_entities if entity["is_projected"]
                    ],
                    "context_entities": context_entities,
                }
            )
        return {
            "projection_id": projection_id,
            "scope": scope,
            "edge": {
                "source_canonical_id": edge_row["source_canonical_id"],
                "target_canonical_id": edge_row["target_canonical_id"],
                "source_name": edge_row["source_name"],
                "target_name": edge_row["target_name"],
                "category_pair": edge_row["category_pair"],
                "weight": int(edge_row["sentence_count"]),
                "document_count": int(edge_row["document_count"]),
            },
            "total": len(observations),
            "offset": offset,
            "limit": limit,
            "items": items,
        }

    @staticmethod
    def with_public_urls(payload: dict, base_url: str) -> dict:
        prefix = f"{base_url.rstrip('/')}/files/networks"

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
