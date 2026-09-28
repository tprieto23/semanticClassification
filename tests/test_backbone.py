import csv
import tempfile
import unittest
from pathlib import Path

import networkx as nx

from src.analysis.backbone import (
    DocumentRecurrentCoreConfig,
    build_document_recurrent_core,
    export_document_recurrent_core,
)
from src.analysis.cooccurrence import MentionRecord, build_sentence_cooccurrence
from src.analysis.projections import SEMANTIC_PROJECTION


class DocumentRecurrentCoreTests(unittest.TestCase):
    @staticmethod
    def _mention(
        document: str,
        sentence: str,
        node_id: str,
        name: str,
        category: str,
        start: int,
        context: str,
    ) -> MentionRecord:
        return MentionRecord(
            document_id=document,
            sentence_id=sentence,
            canonical_id=node_id,
            canonical_name=name,
            category=category,
            text=name,
            start=start,
            end=start + len(name),
            context=context,
            ambiguity="low",
        )

    def _result(self):
        mentions = []
        specs = (
            (
                "d1",
                "s1",
                "P, I, G y X aparecen en una enumeración.",
                (
                    ("p", "Práctica", "PRAC"),
                    ("i", "Infraestructura", "INFRA"),
                    ("g", "Regla", "RUL"),
                    ("x", "Práctica rara", "PRAC"),
                ),
            ),
            (
                "d2",
                "s2",
                "P se articula con I.",
                (("p", "Práctica", "PRAC"), ("i", "Infraestructura", "INFRA")),
            ),
            (
                "d2",
                "s3",
                "P se articula con G.",
                (("p", "Práctica", "PRAC"), ("g", "Regla", "RUL")),
            ),
            (
                "d3",
                "s4",
                "I se articula con G.",
                (("i", "Infraestructura", "INFRA"), ("g", "Regla", "RUL")),
            ),
        )
        for document, sentence, context, entities in specs:
            for index, (node_id, name, category) in enumerate(entities):
                mentions.append(
                    self._mention(
                        document,
                        sentence,
                        node_id,
                        name,
                        category,
                        index * 20,
                        context,
                    )
                )
        return build_sentence_cooccurrence(
            mentions,
            node_categories=SEMANTIC_PROJECTION.node_categories,
            allowed_category_pairs=SEMANTIC_PROJECTION.category_pairs,
        )

    def test_core_filters_nodes_and_calculates_fractional_document_weight(self):
        build = build_document_recurrent_core(
            self._result(),
            DocumentRecurrentCoreConfig(
                minimum_node_document_count=2,
                edge_weighting="fractional-document",
            ),
        )

        self.assertEqual(set(build.graph), {"p", "i", "g"})
        self.assertEqual(build.graph.number_of_edges(), 3)
        self.assertEqual(build.eligible_node_count, 3)
        self.assertEqual(len(build.excluded_nodes), 1)
        self.assertEqual(len(build.excluded_edges), 3)
        edge = build.graph.edges["p", "i"]
        self.assertEqual(edge["sentence_count"], 2)
        self.assertEqual(edge["document_count"], 2)
        self.assertEqual(edge["independent_support_count"], 2)
        self.assertAlmostEqual(edge["fractional_weight"], 4 / 3)
        self.assertAlmostEqual(edge["fractional_document_weight"], 4 / 3)
        self.assertEqual(edge["analysis_weight"], edge["fractional_document_weight"])
        self.assertEqual(edge["confidence_tier"], "transversal")

    def test_selected_weighting_becomes_standard_graph_weight(self):
        build = build_document_recurrent_core(
            self._result(),
            DocumentRecurrentCoreConfig(edge_weighting="document-count"),
        )

        self.assertEqual(build.graph.edges["p", "i"]["weight"], 2.0)
        self.assertEqual(build.graph.nodes["p"]["strength"], 4.0)

    def test_export_summarizes_views_and_writes_only_canonical_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            payload = export_document_recurrent_core(
                self._result(),
                output,
                scope="language:es",
                projection=SEMANTIC_PROJECTION,
                config=DocumentRecurrentCoreConfig(),
            )

            self.assertEqual(
                set(payload["component_views"]), {"all-components", "main-component"}
            )
            self.assertEqual(len(payload["component_views"]["all-components"]), 9)
            self.assertEqual(payload["base_network"]["canonical_nodes"], 4)
            self.assertEqual(payload["base_network"]["edge_incident_nodes"], 4)
            self.assertEqual(payload["base_network"]["isolated_nodes"], 0)
            graphml = output / "network.graphml"
            self.assertTrue(graphml.exists())
            graph = nx.read_graphml(graphml)
            self.assertEqual(
                graph.graph["construction_method"], "document-recurrent-core-v1"
            )
            self.assertEqual(graph.graph["edge_weighting"], "fractional-document")
            self.assertIn("analysis_weight", next(iter(graph.edges(data=True)))[2])
            self.assertFalse((output / "backbone").exists())
            with (output / "edges.csv").open(encoding="utf-8", newline="") as file:
                fields = csv.DictReader(file).fieldnames
            self.assertIn("fractional_document_weight", fields)
            self.assertEqual(payload["primary_component_scope"], "main-component")
            self.assertEqual(len(list(output.rglob("*.*"))), 4)


if __name__ == "__main__":
    unittest.main()
