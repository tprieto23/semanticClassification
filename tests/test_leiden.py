import csv
from importlib.util import find_spec
import tempfile
import unittest
from pathlib import Path

import networkx as nx

from src.analysis.leiden import (
    LeidenConfig,
    LeidenError,
    export_leiden_clustering,
)


class LeidenAnalysisTests(unittest.TestCase):
    @staticmethod
    def _graph() -> nx.Graph:
        graph = nx.Graph()
        for node, category in (
            ("a", "PRAC"),
            ("b", "PRAC"),
            ("c", "RUL"),
            ("d", "INFRA"),
            ("e", "INFRA"),
            ("f", "RUL"),
        ):
            graph.add_node(
                node,
                canonical_id=node,
                canonical_name=f"Entidad {node}",
                label=f"Entidad {node}",
                category=category,
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
        return graph

    @unittest.skipUnless(
        find_spec("igraph") is not None and find_spec("leidenalg") is not None,
        "igraph/leidenalg no instalado en el entorno de test",
    )
    def test_export_is_reproducible_and_gephi_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "network.graphml"
            nx.write_graphml(self._graph(), source)
            first_dir = Path(temporary) / "first"
            second_dir = Path(temporary) / "second"

            first = export_leiden_clustering(
                source, first_dir, config=LeidenConfig(seed=42)
            )
            second = export_leiden_clustering(
                source, second_dir, config=LeidenConfig(seed=42)
            )

            self.assertEqual(first["status"], "completed")
            self.assertEqual(first["counts"]["communities"], 2)
            self.assertEqual(first["counts"], second["counts"])
            self.assertEqual(first["community_sizes"], second["community_sizes"])
            self.assertEqual((first_dir / "network_clustered.graphml").exists(), True)
            clustered = nx.read_graphml(first_dir / "network_clustered.graphml")
            attributes = next(iter(clustered.nodes(data=True)))[1]
            self.assertIn("modularity_class", attributes)
            self.assertIn("community_id", attributes)
            self.assertIn("community_color", attributes)
            with (first_dir / "network_clustered_members.csv").open(
                encoding="utf-8", newline=""
            ) as file:
                fields = csv.DictReader(file).fieldnames
            self.assertIn("modularity_class", fields)
            self.assertIn("community_id", fields)

    def test_graph_without_edges_exports_singletons(self) -> None:
        graph = nx.Graph()
        graph.add_node("only", canonical_id="only", canonical_name="Único")
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "network.graphml"
            output = Path(temporary) / "output"
            nx.write_graphml(graph, source)
            payload = export_leiden_clustering(source, output, config=LeidenConfig())

        self.assertEqual(payload["status"], "trivial")
        self.assertEqual(payload["counts"]["communities"], 1)
        self.assertEqual(payload["counts"]["singleton_communities"], 1)

    def test_invalid_weight_is_rejected(self) -> None:
        graph = nx.Graph()
        graph.add_edge("a", "b", weight=0)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "network.graphml"
            nx.write_graphml(graph, source)
            with self.assertRaises(LeidenError):
                export_leiden_clustering(
                    source, Path(temporary) / "output", config=LeidenConfig()
                )


if __name__ == "__main__":
    unittest.main()
