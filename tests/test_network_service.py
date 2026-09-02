import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import networkx as nx
from pydantic import ValidationError

from src.api.main import app
from src.api.schemas.network import (
    AnalyticalNetworkBuildResponse,
    LeidenClusteringRequest,
    LeidenClusteringResponse,
    NetworkBuildRequest,
    TypedNetworkBuildRequest,
    TypedNetworkBuildResponse,
)
from src.analysis.backbone import DocumentRecurrentCoreConfig
from src.analysis.cooccurrence import MentionRecord
from src.config import settings
from src.services.network import NetworkArtifactsNotFound, NetworkService


class NetworkServiceTests(unittest.TestCase):
    @staticmethod
    def _mention(node_id: str, name: str, category: str, start: int) -> MentionRecord:
        return MentionRecord(
            document_id="00000000-0000-0000-0000-000000000001",
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
        request_schema = paths["/analysis/network"]["post"]["requestBody"]
        self.assertIn("application/json", request_schema["content"])

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

    def test_scope_separates_incubator_and_language_combinations(self) -> None:
        self.assertEqual(NetworkService._scope(), ("corpus", Path("corpus")))
        self.assertEqual(
            NetworkService._scope(language="es"),
            ("language:es", Path("corpus/language-es")),
        )
        self.assertEqual(
            NetworkService._scope(incubator_number=4),
            ("incubator:4", Path("incubator-4")),
        )
        self.assertEqual(
            NetworkService._scope(incubator_number=4, language="es"),
            (
                "incubator:4,language:es",
                Path("incubator-4/language-es"),
            ),
        )

    def test_latest_is_parameter_specific(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "corpus" / "w3-no-isolates"
            target.mkdir(parents=True)
            expected = {
                "scope": "corpus",
                "outputs": {"graphml": "corpus/w3-no-isolates/g3.graphml"},
            }
            (target / "api_response.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )

            with patch.object(settings, "STORAGE_NETWORK", root):
                self.assertEqual(
                    NetworkService.latest(minimum_weight=3, include_isolates=False),
                    expected,
                )
                with self.assertRaises(NetworkArtifactsNotFound):
                    NetworkService.latest(minimum_weight=1, include_isolates=True)

    def test_latest_resolves_language_specific_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "corpus" / "language-es" / "w1-isolates"
            target.mkdir(parents=True)
            expected = {
                "scope": "language:es",
                "outputs": {"graphml": "corpus/language-es/w1-isolates/g1.graphml"},
            }
            (target / "api_response.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )

            with patch.object(settings, "STORAGE_NETWORK", root):
                self.assertEqual(NetworkService.latest(language="es"), expected)

    def test_projection_paths_do_not_collide_with_historical_networks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(settings, "STORAGE_NETWORK", root):
                scope, target = NetworkService._projection_target_dir(
                    "prac-infra-gov-v1",
                    minimum_weight=1,
                    include_isolates=True,
                    language="es",
                )

        self.assertEqual(scope, "language:es")
        self.assertEqual(
            target,
            root
            / "corpus"
            / "language-es"
            / "projections"
            / "prac-infra-gov-v1"
            / "w1-isolates",
        )

    def test_construction_path_encodes_all_method_parameters(self) -> None:
        from src.analysis.backbone import DocumentRecurrentCoreConfig

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = DocumentRecurrentCoreConfig(
                minimum_node_document_count=3,
                edge_weighting="document-count",
                include_minor_components=False,
            )
            with patch.object(settings, "STORAGE_NETWORK", root):
                scope, target = NetworkService._construction_target_dir(
                    "prac-infra-gov-v1", config, language="es"
                )

        self.assertEqual(scope, "language:es")
        self.assertEqual(
            target,
            root
            / "corpus/language-es/projections/prac-infra-gov-v1/constructions"
            / "document-recurrent-core-v1/node-documents-3"
            / "edge-weight-document-count/main-component-only",
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

    def test_latest_projection_is_parameter_specific(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = (
                root / "corpus" / "projections" / "prac-infra-gov-v1" / "w1-isolates"
            )
            target.mkdir(parents=True)
            expected = {
                "scope": "corpus",
                "outputs": {
                    "graphml": "corpus/projections/prac-infra-gov-v1/w1-isolates/views/all/g1.graphml"
                },
            }
            (target / "api_response.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )

            with patch.object(settings, "STORAGE_NETWORK", root):
                self.assertEqual(
                    NetworkService.latest_projection("prac-infra-gov-v1"),
                    expected,
                )

    def test_projection_build_exports_master_evidence_and_nine_views(self) -> None:
        mentions = [
            self._mention("p", "Práctica", "PRAC", 0),
            self._mention("i", "Infraestructura", "INFRA", 20),
            self._mention("g", "Gobernanza", "GOV", 40),
            self._mention("c", "Actor", "CHAR", 60),
            self._mention("l", "Lugar", "LOC", 80),
        ]
        visual_summary = {
            "nodes": 3,
            "edges": 3,
            "components": 1,
            "nodes_by_category": {"PRAC": 1, "INFRA": 1, "GOV": 1},
            "edges_by_category_pair": {
                "PRAC--INFRA": 1,
                "PRAC--GOV": 1,
                "INFRA--GOV": 1,
            },
            "top_nodes_by_strength": [],
            "outputs": {"graphml": "g1.graphml"},
        }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(settings, "STORAGE_NETWORK", root),
                patch("src.services.network.load_db_mentions", return_value=mentions),
                patch.object(
                    NetworkService,
                    "_coverage",
                    return_value={
                        "documents_included": 1,
                        "documents_total": 1,
                        "excluded_by_status": {},
                    },
                ),
                patch(
                    "src.analysis.network_visualization.generate_visualizations",
                    return_value=visual_summary,
                ) as generate,
            ):
                payload = NetworkService.build_projection(Mock(), "prac-infra-gov-v1")
                evidence = NetworkService.edge_evidence("prac-infra-gov-v1", "p", "i")

            target = (
                root / "corpus" / "projections" / "prac-infra-gov-v1" / "w1-isolates"
            )
            self.assertTrue((target / "evidence" / "sentence_entities.csv").exists())
            self.assertTrue((target / "evidence" / "edge_observations.csv").exists())
            self.assertTrue((target / "projection_manifest.json").exists())

        self.assertEqual(generate.call_count, 9)
        self.assertEqual(
            set(payload["views"]),
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
        self.assertEqual(payload["counts"]["source_mentions"], 5)
        self.assertEqual(payload["counts"]["projected_mentions"], 3)
        self.assertEqual(evidence["edge"]["category_pair"], "PRAC--INFRA")
        self.assertEqual(len(evidence["items"][0]["projected_entities"]), 3)
        self.assertEqual(len(evidence["items"][0]["context_entities"]), 5)
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
                patch.object(settings, "STORAGE_NETWORK", root),
                patch("src.services.network.load_db_mentions", return_value=mentions),
                patch.object(
                    NetworkService,
                    "_coverage",
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

            target = (
                root
                / "corpus/language-es/projections/prac-infra-gov-v1/constructions"
                / "document-recurrent-core-v1/node-documents-2"
                / "edge-weight-fractional-document/with-minor-components"
            )
            self.assertTrue((target / "evidence/edge_observations.csv").exists())
            self.assertTrue(
                (target / "views/all-components/all/network.graphml").exists()
            )
            self.assertTrue((target / "construction_manifest.json").exists())

        self.assertEqual(payload["analytical_network"]["canonical_nodes"], 3)
        self.assertEqual(payload["analytical_network"]["undirected_edges"], 3)
        self.assertEqual(len(payload["component_views"]["all-components"]), 9)
        AnalyticalNetworkBuildResponse.model_validate(payload)

    def test_leiden_service_clusters_existing_graph_and_uses_cache(self) -> None:
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
            with patch.object(settings, "STORAGE_NETWORK", root):
                _, target = NetworkService._construction_target_dir(
                    "prac-infra-gov-v1",
                    DocumentRecurrentCoreConfig(minimum_node_document_count=2),
                    language="es",
                )
                source = target / "views" / "main-component" / "all"
                source.mkdir(parents=True)
                nx.write_graphml(graph, source / "network.graphml")
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
                clustered_path = root / payload["outputs"]["clustered_graphml"]
                self.assertTrue(clustered_path.exists())

        self.assertEqual(payload["status"], "completed")
        self.assertFalse(payload["cached"])
        self.assertTrue(cached["cached"])
        LeidenClusteringResponse.model_validate(payload)

    def test_public_urls_only_expose_network_mount(self) -> None:
        payload = {
            "scope": "corpus",
            "outputs": {
                "graphml": "corpus/w1-isolates/g1.graphml",
                "interactive_html": "corpus/w1-isolates/g1_interactive.html",
            },
        }

        response = NetworkService.with_public_urls(payload, "http://testserver/")

        self.assertEqual(
            response["outputs"]["graphml"],
            "http://testserver/files/networks/corpus/w1-isolates/g1.graphml",
        )
        self.assertNotIn("s3/", response["outputs"]["interactive_html"])

    def test_public_urls_are_rewritten_inside_projection_views(self) -> None:
        payload = {
            "outputs": {"sentences_csv": "corpus/projection/sentences.csv"},
            "views": {
                "all": {
                    "outputs": {"graphml": "corpus/projection/views/all/g1.graphml"}
                }
            },
        }

        response = NetworkService.with_public_urls(payload, "http://testserver/")

        self.assertEqual(
            response["views"]["all"]["outputs"]["graphml"],
            "http://testserver/files/networks/corpus/projection/views/all/g1.graphml",
        )


if __name__ == "__main__":
    unittest.main()
