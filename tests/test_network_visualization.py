import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.analysis.network_visualization import (
    build_free_layout,
    generate_visualizations,
    load_core_network,
)

NODE_FIELDS = (
    "matrix_index",
    "category_index",
    "canonical_id",
    "canonical_name",
    "category",
    "mention_count",
    "sentence_count",
    "document_count",
    "ambiguity_low",
    "ambiguity_medium",
    "ambiguity_high",
    "ambiguity_other",
)


class NetworkVisualizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.analysis_dir = Path(self.temporary.name) / "analysis"
        self.analysis_dir.mkdir()
        self.document_id = "00000000-0000-0000-0000-000000000001"
        (self.analysis_dir / "summary.json").write_text(
            json.dumps({"scope": f"document:{self.document_id}"}), encoding="utf-8"
        )
        self.nodes = [
            self._node("a", "Actores", "CHAR", 0),
            self._node("p", "Minería", "PRAC", 1),
            self._node("i", "Draga", "INFRA", 2),
            self._node("g", "Ley", "RUL", 3),
            self._node("l", "Territorio", "LOC", 4),
        ]
        self._write_csv(self.analysis_dir / "nodes.csv", NODE_FIELDS, self.nodes)
        edge_fields = (
            "source_canonical_id",
            "target_canonical_id",
            "category_pair",
            "sentence_count",
            "document_count",
        )
        self.edges = [
            self._edge("a", "p", "CHAR--PRAC", 5),
            self._edge("p", "l", "LOC--PRAC", 3),
            self._edge("p", "i", "PRAC--INFRA", 2),
            self._edge("i", "g", "INFRA--RUL", 1),
        ]
        self._write_csv(self.analysis_dir / "edges.csv", edge_fields, self.edges)
        self._write_evidence()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _node(self, node_id: str, name: str, category: str, index: int) -> dict:
        return {
            "matrix_index": index,
            "category_index": 0,
            "canonical_id": node_id,
            "canonical_name": name,
            "category": category,
            "mention_count": 5,
            "sentence_count": 4,
            "document_count": 1,
            "ambiguity_low": 5,
            "ambiguity_medium": 0,
            "ambiguity_high": 0,
            "ambiguity_other": 0,
        }

    def _edge(
        self, source: str, target: str, category_pair: str, weight: int
    ) -> dict:
        return {
            "source_canonical_id": source,
            "target_canonical_id": target,
            "category_pair": category_pair,
            "sentence_count": weight,
            "document_count": 1,
        }

    def _write_csv(self, path: Path, fields, rows) -> None:
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def _write_evidence(self) -> None:
        self._write_csv(
            self.analysis_dir / "sentences.csv",
            (
                "matrix_row",
                "document_id",
                "sentence_id",
                "mention_count",
                "unique_node_count",
                "context",
            ),
            [
                {
                    "matrix_row": 0,
                    "document_id": self.document_id,
                    "sentence_id": "s-1",
                    "mention_count": 3,
                    "unique_node_count": 3,
                    "context": "Contexto general de la oración.",
                }
            ],
        )
        self._write_csv(
            self.analysis_dir / "edge_observations.csv",
            (
                "source_canonical_id",
                "target_canonical_id",
                "document_id",
                "sentence_id",
                "context",
                "source_texts",
                "target_texts",
                "source_ambiguities",
                "target_ambiguities",
            ),
            [
                {
                    "source_canonical_id": "a",
                    "target_canonical_id": "p",
                    "document_id": self.document_id,
                    "sentence_id": "s-1",
                    "context": "Los actores practican minería.",
                    "source_texts": "actores",
                    "target_texts": "minería",
                    "source_ambiguities": "low",
                    "target_ambiguities": "low",
                },
                {
                    "source_canonical_id": "p",
                    "target_canonical_id": "l",
                    "document_id": self.document_id,
                    "sentence_id": "s-1",
                    "context": "La minería ocurre en el territorio.",
                    "source_texts": "minería",
                    "target_texts": "territorio",
                    "source_ambiguities": "low",
                    "target_ambiguities": "low",
                },
                {
                    "source_canonical_id": "p",
                    "target_canonical_id": "i",
                    "document_id": self.document_id,
                    "sentence_id": "s-1",
                    "context": "La minería utiliza una draga.",
                    "source_texts": "minería",
                    "target_texts": "draga",
                    "source_ambiguities": "low",
                    "target_ambiguities": "low",
                },
                {
                    "source_canonical_id": "i",
                    "target_canonical_id": "g",
                    "document_id": self.document_id,
                    "sentence_id": "s-1",
                    "context": "La ley regula la draga.",
                    "source_texts": "draga",
                    "target_texts": "ley",
                    "source_ambiguities": "low",
                    "target_ambiguities": "low",
                },
            ],
        )
        self._write_csv(
            self.analysis_dir / "sentence_entities.csv",
            (
                "sentence_row",
                "document_id",
                "sentence_id",
                "canonical_id",
                "canonical_name",
                "category",
                "is_projected",
                "mention_count",
                "texts",
                "ambiguities",
            ),
            [
                {
                    "sentence_row": 0,
                    "document_id": self.document_id,
                    "sentence_id": "s-1",
                    "canonical_id": node["canonical_id"],
                    "canonical_name": node["canonical_name"],
                    "category": node["category"],
                    "is_projected": str(
                        node["category"] in {"PRAC", "INFRA", "RUL"}
                    ).lower(),
                    "mention_count": 1,
                    "texts": node["canonical_name"],
                    "ambiguities": "low",
                }
                for node in self.nodes
            ],
        )

    def test_threshold_builds_edge_induced_core(self) -> None:
        data = load_core_network(self.analysis_dir, minimum_weight=3)

        self.assertEqual(set(data.graph), {"a", "p", "l"})
        self.assertEqual(data.graph.number_of_edges(), 2)
        self.assertEqual(data.graph.nodes["p"]["degree"], 2)
        self.assertEqual(data.graph.nodes["p"]["strength"], 8)

    def test_free_layout_covers_every_category_without_rows(self) -> None:
        data = load_core_network(self.analysis_dir, minimum_weight=1)
        positions = build_free_layout(data.graph)

        self.assertEqual(set(positions), set(data.graph))
        self.assertTrue(all(len(position) == 2 for position in positions.values()))

    def test_complete_network_can_include_isolated_nodes(self) -> None:
        data = load_core_network(
            self.analysis_dir, minimum_weight=3, include_isolates=True
        )

        self.assertEqual(set(data.graph), {"a", "p", "i", "g", "l"})
        self.assertEqual(data.graph.degree("i"), 0)
        self.assertEqual(data.graph.nodes["i"]["strength"], 0)
        self.assertIn("i", build_free_layout(data.graph))

    def test_generation_creates_flat_outputs_and_pair_context(self) -> None:
        output_dir = Path(self.temporary.name) / "outputs"

        summary = generate_visualizations(
            self.analysis_dir, output_dir, minimum_weight=3
        )

        expected = (
            "g3_free.png",
            "g3_free.svg",
            "g3_interactive.html",
            "g3_graph.json",
            "g3.graphml",
            "g3_nodes.csv",
            "g3_edges.csv",
            "g3_summary.json",
        )
        self.assertTrue(all((output_dir / name).exists() for name in expected))
        self.assertEqual(summary["nodes"], 3)
        html = (output_dir / "g3_interactive.html").read_text(encoding="utf-8")
        self.assertIn("Los actores practican minería", html)
        self.assertNotIn("Capas", html)
        self.assertNotIn("Macrocapa", html)
        self.assertNotIn("__NETWORK_DATA__", html)

    def test_complete_generation_exports_isolated_nodes(self) -> None:
        output_dir = Path(self.temporary.name) / "complete_outputs"

        summary = generate_visualizations(
            self.analysis_dir,
            output_dir,
            minimum_weight=1,
            include_isolates=True,
        )

        self.assertTrue(summary["includes_isolates"])
        self.assertEqual(summary["nodes"], 5)
        self.assertTrue((output_dir / "g1_nodes.csv").exists())
        self.assertTrue((output_dir / "g1_interactive.html").exists())

    def test_typed_view_filters_nodes_pairs_and_exposes_normalized_evidence(
        self,
    ) -> None:
        output_dir = Path(self.temporary.name) / "typed_outputs"

        summary = generate_visualizations(
            self.analysis_dir,
            output_dir,
            minimum_weight=1,
            include_isolates=True,
            node_categories=("PRAC", "INFRA", "RUL"),
            allowed_category_pairs=("PRAC--INFRA", "INFRA--RUL"),
        )

        self.assertEqual(summary["nodes"], 3)
        self.assertEqual(summary["edges"], 2)
        self.assertEqual(
            set(summary["edges_by_category_pair"]),
            {"PRAC--INFRA", "INFRA--RUL"},
        )
        payload = json.loads(
            (output_dir / "g1_graph.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["categoryOrder"], ["PRAC", "INFRA", "RUL"])
        self.assertTrue(all(edge["documentCount"] == 1 for edge in payload["edges"]))
        sentence = payload["sentencesByKey"][f"{self.document_id}::s-1"]
        self.assertEqual(len(sentence["projectedEntities"]), 3)
        self.assertEqual(len(sentence["contextEntities"]), 5)


if __name__ == "__main__":
    unittest.main()
