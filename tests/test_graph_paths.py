import os
import unittest
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from src.analysis.graph_paths import (
    backbone_filename,
    base_dir,
    communities_csv_path,
    edges_csv_path,
    graph_scope_dir,
    graphml_path,
    json_path,
    leiden_filename,
    nodes_csv_path,
    red_plana_filename,
)


class GraphPathsTests(unittest.TestCase):
    def test_graph_scope_dir_corpus(self) -> None:
        self.assertEqual(
            graph_scope_dir("corpus", None, "es"),
            Path("corpus/es"),
        )

    def test_graph_scope_dir_incubator(self) -> None:
        self.assertEqual(
            graph_scope_dir("incubators", 3, "en"),
            Path("incubators/3/en"),
        )

    def test_graph_scope_dir_document(self) -> None:
        doc_id = uuid4()
        self.assertEqual(
            graph_scope_dir("documents", doc_id, "all"),
            Path(f"documents/{doc_id}"),
        )

    def test_graph_scope_dir_rejects_invalid_scope(self) -> None:
        with self.assertRaises(ValueError):
            graph_scope_dir("invalid", None, "es")

    def test_graph_scope_dir_rejects_missing_scope_id(self) -> None:
        with self.assertRaises(ValueError):
            graph_scope_dir("incubators", None, "es")

    def test_red_plana_filename(self) -> None:
        self.assertEqual(
            red_plana_filename(1, True),
            "main_network",
        )
        self.assertEqual(
            red_plana_filename(3, False),
            "main_network",
        )

    def test_backbone_filename_raw_threshold(self) -> None:
        self.assertEqual(
            backbone_filename(
                "prac-infra-gov-v1",
                {
                    "method": "raw-threshold-v1",
                    "minimum_weight": 2,
                    "include_isolates": False,
                },
            ),
            "backbone_prac-infra-gov-v1",
        )

    def test_backbone_filename_document_recurrent_core(self) -> None:
        self.assertEqual(
            backbone_filename(
                "prac-infra-gov-v1",
                {
                    "method": "document-recurrent-core-v1",
                    "minimum_node_document_count": 2,
                    "edge_weighting": "fractional-document",
                    "include_minor_components": True,
                },
            ),
            "backbone_prac-infra-gov-v1",
        )

    def test_leiden_filename(self) -> None:
        backbone = backbone_filename(
            "prac-infra-gov-v1",
            {
                "method": "document-recurrent-core-v1",
                "minimum_node_document_count": 2,
                "edge_weighting": "fractional-document",
                "include_minor_components": True,
            },
        )
        self.assertEqual(
            leiden_filename(
                backbone,
                {
                    "method": "leiden-v1",
                    "objective_function": "modularity",
                    "resolution": 1.0,
                    "seed": 42,
                    "iterations": -1,
                    "weight_attribute": "weight",
                },
            ),
            "leiden_prac-infra-gov-v1",
        )

    def test_path_helpers(self) -> None:
        name = red_plana_filename(1, True)
        self.assertEqual(
            graphml_path("corpus", None, "es", name),
            base_dir("graphml", "corpus", None, "es") / "main_network.graphml",
        )
        self.assertEqual(
            json_path("corpus", None, "es", name),
            base_dir("json", "corpus", None, "es") / "main_network.json",
        )
        self.assertEqual(
            nodes_csv_path("corpus", None, "es", name),
            base_dir("csv", "corpus", None, "es") / "main_network_nodes.csv",
        )
        self.assertEqual(
            edges_csv_path("corpus", None, "es", name),
            base_dir("csv", "corpus", None, "es") / "main_network_edges.csv",
        )
        self.assertEqual(
            communities_csv_path("corpus", None, "es", name),
            base_dir("csv", "corpus", None, "es") / "main_network_communities.csv",
        )


if __name__ == "__main__":
    unittest.main()
