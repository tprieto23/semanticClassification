import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

import networkx as nx
from pydantic import ValidationError

from src.analysis.cooccurrence import MentionRecord
from src.api.main import app
from src.api.schemas.network import (
    AnalyticalNetworkBuildResponse,
    LeidenClusteringRequest,
    LeidenClusteringResponse,
    NetworkBuildRequest,
    NetworkBuildResponse,
    TypedNetworkBuildRequest,
    TypedNetworkBuildResponse,
)
from src.config import settings
from src.services.network import NetworkArtifactsNotFound, NetworkService, _graph_scope


class NetworkServiceTests(unittest.TestCase):
    @staticmethod
    def _mention(
        node_id: str,
        name: str,
        category: str,
        start: int,
        document_id: str | None = None,
    ) -> MentionRecord:
        return MentionRecord(
            document_id=document_id or "00000000-0000-0000-0000-000000000001",
            sentence_id="s-1",
            canonical_id=node_id,
            canonical_name=name,
            category=category,
            text=name,
            start=start,
            end=start + len(name),
            context="Contexto completo",
            ambiguity="low",
        )

    def test_openapi_exposes_all_network_endpoints(self) -> None:
        paths = app.openapi()["paths"]

        self.assertIn("post", paths["/analysis/network"])
        self.assertIn("get", paths["/analysis/network/latest"])
        self.assertIn("post", paths["/documents/{document_id}/network"])
        self.assertIn("post", paths["/analysis/network/projections/{projection_id}"])
        self.assertIn(
            "get", paths["/analysis/network/projections/{projection_id}/latest"]
        )
        self.assertIn(
            "get", paths["/analysis/network/projections/{projection_id}/views"]
        )
        self.assertIn(
            "get",
            paths[
                "/analysis/network/projections/{projection_id}/edges/{source_id}/{target_id}/evidence"
            ],
        )
        self.assertIn(
            "post",
            paths["/documents/{document_id}/network/projections/{projection_id}"],
        )
        self.assertIn(
            "post",
            paths["/analysis/network/projections/{projection_id}/clusterings/leiden"],
        )

    def test_build_request_accepts_all_or_specific_filters(self) -> None:
        all_incubators = NetworkBuildRequest(incubator_number="all", language=" ES ")
        one_incubator = NetworkBuildRequest(incubator_number=4, language="es")

        self.assertEqual(all_incubators.incubator_number, "all")
        self.assertEqual(all_incubators.language, "es")
        self.assertEqual(one_incubator.incubator_number, 4)
        with self.assertRaises(ValidationError):
            NetworkBuildRequest(incubator_number=9, language="es")
        with self.assertRaises(ValidationError):
            NetworkBuildRequest(incubator_number="all", language="../../tmp")

    def test_typed_request_discriminates_construction_methods(self) -> None:
        request = TypedNetworkBuildRequest.model_validate(
            {
                "incubator_number": "all",
                "language": "es",
                "construction": {
                    "method": "document-recurrent-core-v1",
                    "minimum_node_document_count": 2,
                    "edge_weighting": "fractional-document",
                    "include_minor_components": True,
                },
            }
        )

        self.assertEqual(request.construction.method, "document-recurrent-core-v1")
        with self.assertRaises(ValidationError):
            TypedNetworkBuildRequest.model_validate(
                {
                    "construction": {
                        "method": "document-recurrent-core-v1",
                        "edge_weighting": "invented",
                    }
                }
            )

    def test_leiden_request_validates_reproducible_configuration(self) -> None:
        request = LeidenClusteringRequest.model_validate(
            {
                "incubator_number": "all",
                "language": " ES ",
                "construction": {
                    "method": "document-recurrent-core-v1",
                    "minimum_node_document_count": 2,
                    "edge_weighting": "fractional-document",
                    "include_minor_components": True,
                },
                "component_scope": "main-component",
                "view": "all",
                "configuration": {
                    "method": "leiden-v1",
                    "objective_function": "modularity",
                    "resolution": 1.0,
                    "seed": 42,
                    "iterations": -1,
                    "weight_attribute": "weight",
                },
            }
        )
        self.assertEqual(request.language, "es")
        self.assertEqual(request.configuration.seed, 42)
        with self.assertRaises(ValidationError):
            LeidenClusteringRequest.model_validate(
                {
                    "construction": {"method": "document-recurrent-core-v1"},
                    "configuration": {"resolution": 0},
                }
            )

    def test_graph_scope_helper(self) -> None:
        self.assertEqual(_graph_scope(), ("corpus", None, "all"))
        self.assertEqual(_graph_scope(language="es"), ("corpus", None, "es"))
        self.assertEqual(_graph_scope(incubator_number=4), ("incubators", 4, "all"))
        self.assertEqual(
            _graph_scope(incubator_number=4, language="es"),
            ("incubators", 4, "es"),
        )

    def test_latest_reads_the_stable_official_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "json" / "corpus" / "all"
            target.mkdir(parents=True)
            expected = {
                "scope": "corpus",
                "outputs": {"graphml": "graphml/corpus/all/main_network.graphml"},
            }
            (target / "main_network.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )

            with patch.object(settings, "STORAGE_GRAPHS", root):
                self.assertEqual(NetworkService.latest(), expected)

    def test_latest_resolves_language_specific_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "json" / "corpus" / "es"
            target.mkdir(parents=True)
            expected = {
                "scope": "corpus:all:es",
                "outputs": {"graphml": "graphml/corpus/es/main_network.graphml"},
            }
            (target / "main_network.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )

            with patch.object(settings, "STORAGE_GRAPHS", root):
                self.assertEqual(
                    NetworkService.latest(
                        minimum_weight=3, include_isolates=False, language="es"
                    ),
                    expected,
                )

    def test_main_network_publishes_only_canonical_format_artifacts(self) -> None:
        mentions = [
            self._mention("p", "Práctica", "PRAC", 0),
            self._mention("i", "Infraestructura", "INFRA", 20),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(settings, "STORAGE_GRAPHS", root),
                patch("src.services.network.load_db_mentions", return_value=mentions),
                patch(
                    "src.services.network._coverage",
                    return_value={
                        "documents_included": 1,
                        "documents_total": 1,
                        "excluded_by_status": {},
                    },
                ),
            ):
                payload = NetworkService.build(Mock(), language="es")

            base = "main_network"
            self.assertTrue((root / "graphml/corpus/es" / f"{base}.graphml").exists())
            self.assertTrue((root / "json/corpus/es" / f"{base}.json").exists())
            self.assertTrue((root / "csv/corpus/es" / f"{base}_nodes.csv").exists())
            self.assertTrue((root / "csv/corpus/es" / f"{base}_edges.csv").exists())
            self.assertEqual(len(list(root.rglob("*.*"))), 4)
        NetworkBuildResponse.model_validate(payload)

    def test_projection_paths_are_stable_by_name(self) -> None:
        from src.analysis.graph_paths import graphml_path, json_path

        self.assertEqual(
            graphml_path("corpus", None, "es", "backbone_prac-infra-gov-v1"),
            Path("s3/graphs/graphml/corpus/es/backbone_prac-infra-gov-v1.graphml"),
        )
        self.assertEqual(
            json_path("corpus", None, "es", "backbone_prac-infra-gov-v1"),
            Path("s3/graphs/json/corpus/es/backbone_prac-infra-gov-v1.json"),
        )

    def test_projection_registry_exposes_master_and_partial_views(self) -> None:
        payload = NetworkService.projection_views("prac-infra-gov-v1")

        self.assertEqual(
            payload["projection"]["node_categories"], ["PRAC", "INFRA", "GOV"]
        )
        self.assertEqual(len(payload["projection"]["category_pairs"]), 6)
        self.assertEqual(
            {view["id"] for view in payload["views"]},
            {
                "all",
                "cross",
                "intra",
                "prac-prac",
                "infra-infra",
                "gov-gov",
                "prac-infra",
                "prac-gov",
                "infra-gov",
            },
        )

    def test_latest_projection_reads_the_stable_backbone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "json" / "corpus" / "all"
            target.mkdir(parents=True)
            expected = {
                "scope": "corpus",
                "outputs": {
                    "graphml": "graphml/corpus/all/backbone_prac-infra-gov-v1.graphml"
                },
            }
            (target / "backbone_prac-infra-gov-v1.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )

            with patch.object(settings, "STORAGE_GRAPHS", root):
                self.assertEqual(
                    NetworkService.latest_projection("prac-infra-gov-v1"),
                    expected,
                )

    def test_projection_build_publishes_only_canonical_format_artifacts(self) -> None:
        mentions = [
            self._mention("p", "Práctica", "PRAC", 0),
            self._mention("i", "Infraestructura", "INFRA", 20),
            self._mention("g", "Gobernanza", "GOV", 40),
            self._mention("c", "Actor", "CHAR", 60),
            self._mention("l", "Lugar", "LOC", 80),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(settings, "STORAGE_GRAPHS", root),
                patch("src.services.network.load_db_mentions", return_value=mentions),
                patch(
                    "src.services.network._coverage",
                    return_value={
                        "documents_included": 1,
                        "documents_total": 1,
                        "excluded_by_status": {},
                    },
                ),
            ):
                payload = NetworkService.build_projection(Mock(), "prac-infra-gov-v1")

            stem = "backbone_prac-infra-gov-v1"
            self.assertTrue((root / "graphml/corpus/all" / f"{stem}.graphml").exists())
            self.assertTrue((root / "json/corpus/all" / f"{stem}.json").exists())
            self.assertTrue((root / "csv/corpus/all" / f"{stem}_nodes.csv").exists())
            self.assertTrue((root / "csv/corpus/all" / f"{stem}_edges.csv").exists())
            self.assertEqual(len(list(root.rglob("*.*"))), 4)

        self.assertEqual(payload["counts"]["mentions"], 5)
        self.assertEqual(payload["counts"]["projected_mentions"], 3)
        TypedNetworkBuildResponse.model_validate(payload)

    def test_projection_build_can_construct_document_recurrent_core(self) -> None:
        first_document = "00000000-0000-0000-0000-000000000001"
        second_document = "00000000-0000-0000-0000-000000000002"
        base_mentions = [
            self._mention("p", "Práctica", "PRAC", 0),
            self._mention("i", "Infraestructura", "INFRA", 20),
            self._mention("g", "Gobernanza", "GOV", 40),
        ]
        mentions = [
            replace(mention, document_id=first_document, sentence_id="s-1")
            for mention in base_mentions
        ] + [
            replace(mention, document_id=second_document, sentence_id="s-2")
            for mention in base_mentions
        ]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(settings, "STORAGE_GRAPHS", root),
                patch("src.services.network.load_db_mentions", return_value=mentions),
                patch(
                    "src.services.network._coverage",
                    return_value={
                        "documents_included": 2,
                        "documents_total": 2,
                        "excluded_by_status": {},
                    },
                ),
            ):
                payload = NetworkService.build_projection(
                    Mock(),
                    "prac-infra-gov-v1",
                    language="es",
                    construction={
                        "method": "document-recurrent-core-v1",
                        "minimum_node_document_count": 2,
                        "edge_weighting": "fractional-document",
                        "include_minor_components": True,
                    },
                )

            stem = "backbone_prac-infra-gov-v1"
            self.assertTrue((root / "graphml/corpus/es" / f"{stem}.graphml").exists())
            self.assertTrue((root / "json/corpus/es" / f"{stem}.json").exists())
            self.assertTrue((root / "csv/corpus/es" / f"{stem}_nodes.csv").exists())
            self.assertTrue((root / "csv/corpus/es" / f"{stem}_edges.csv").exists())
            self.assertEqual(len(list(root.rglob("*.*"))), 4)

        self.assertEqual(payload["counts"]["canonical_nodes"], 3)
        self.assertEqual(payload["counts"]["undirected_edges"], 3)
        AnalyticalNetworkBuildResponse.model_validate(payload)

    def test_leiden_service_clusters_existing_graph_and_uses_cache(self) -> None:
        try:
            import igraph  # noqa: F401
            import leidenalg  # noqa: F401
        except ImportError:
            self.skipTest("igraph/leidenalg no instalado en el entorno de test")

        graph = nx.Graph()
        for node in ("a", "b", "c", "d", "e", "f"):
            graph.add_node(
                node,
                canonical_id=node,
                canonical_name=f"Entidad {node}",
                label=f"Entidad {node}",
                category="PRAC",
                component=1,
                component_size=6,
                degree=2,
                strength=2.0,
            )
        for source, target in (
            ("a", "b"),
            ("b", "c"),
            ("c", "a"),
            ("d", "e"),
            ("e", "f"),
            ("f", "d"),
        ):
            graph.add_edge(
                source,
                target,
                weight=1.0,
                analysis_weight=1.0,
                sentence_count=1,
                document_count=1,
            )

        construction = {
            "method": "document-recurrent-core-v1",
            "minimum_node_document_count": 2,
            "edge_weighting": "fractional-document",
            "include_minor_components": True,
        }
        configuration = {
            "method": "leiden-v1",
            "objective_function": "modularity",
            "resolution": 1.0,
            "seed": 42,
            "iterations": -1,
            "weight_attribute": "weight",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(settings, "STORAGE_GRAPHS", root):
                source = root / "graphml/corpus/es/backbone_prac-infra-gov-v1.graphml"
                source.parent.mkdir(parents=True)
                nx.write_graphml(graph, source)
                payload = NetworkService.cluster_projection_leiden(
                    "prac-infra-gov-v1",
                    construction=construction,
                    component_scope="main-component",
                    view_id="all",
                    configuration=configuration,
                    language="es",
                )
                cached = NetworkService.cluster_projection_leiden(
                    "prac-infra-gov-v1",
                    construction=construction,
                    component_scope="main-component",
                    view_id="all",
                    configuration=configuration,
                    language="es",
                )
                clustered_path = root / payload["outputs"]["graphml"]
                self.assertTrue(clustered_path.exists())

        self.assertEqual(payload["status"], "completed")
        self.assertFalse(payload["cached"])
        self.assertTrue(cached["cached"])
        LeidenClusteringResponse.model_validate(payload)

    def test_public_urls_expose_graphs_mount(self) -> None:
        payload = {
            "scope": "corpus",
            "outputs": {
                "graphml": "graphml/corpus/es/main_network.graphml",
            },
        }

        response = NetworkService.with_public_urls(payload, "http://testserver/")

        self.assertEqual(
            response["outputs"]["graphml"],
            "http://testserver/files/graphs/graphml/corpus/es/main_network.graphml",
        )

    def test_edge_evidence_queries_postgres(self) -> None:
        rows = [
            SimpleNamespace(
                document_id=UUID("00000000-0000-0000-0000-000000000001"),
                sentence_id="s-1",
                context="Los mineros trabajan en la comunidad.",
                canonical_id=UUID("00000000-0000-0000-0000-000000000010"),
                canonical_name="minero",
                category="CHAR",
                mention_text="mineros",
                ambiguity="low",
            ),
            SimpleNamespace(
                document_id=UUID("00000000-0000-0000-0000-000000000001"),
                sentence_id="s-1",
                context="Los mineros trabajan en la comunidad.",
                canonical_id=UUID("00000000-0000-0000-0000-000000000011"),
                canonical_name="comunidad",
                category="CHAR",
                mention_text="comunidad",
                ambiguity="low",
            ),
        ]
        db = Mock()
        db.execute.return_value.all.return_value = rows

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "json" / "corpus" / "all"
            target.mkdir(parents=True)
            (target / "backbone_prac-infra-gov-v1.json").write_text(
                json.dumps({"scope": "corpus"}), encoding="utf-8"
            )
            with patch.object(settings, "STORAGE_GRAPHS", root):
                evidence = NetworkService.edge_evidence(
                    db=db,
                    projection_id="prac-infra-gov-v1",
                    source_id="00000000-0000-0000-0000-000000000010",
                    target_id="00000000-0000-0000-0000-000000000011",
                )

        self.assertEqual(evidence["total"], 1)
        self.assertEqual(len(evidence["items"][0]["context_entities"]), 2)


if __name__ == "__main__":
    unittest.main()
