import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import networkx as nx

from src.analysis.leiden import graph_file_sha256
from src.config import settings
from src.services.semantic_nodes import (
    SemanticNodeError,
    SemanticNodeService,
    _read_partition,
)


class SemanticNodeTests(unittest.TestCase):
    def test_source_lists_communities_and_uses_clustered_graph_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            graph_path = Path(temporary) / "leiden.graphml"
            metadata_path = Path(temporary) / "leiden.json"
            graph = nx.Graph()
            graph.graph["source_graph_sha256"] = "source-hash"
            graph.add_node(str(uuid4()), community_id="C001")
            graph.add_node(str(uuid4()), community_id="C001")
            graph.add_node(str(uuid4()), community_id="C002")
            nx.write_graphml(graph, graph_path)
            metadata_path.write_text(json.dumps({
                "status": "completed",
                "source": {"graphml_sha256": "source-hash"},
                "configuration": {"resolution": 1.0},
            }), encoding="utf-8")

            with patch("src.services.semantic_nodes._artifacts", return_value=(
                graph_path, metadata_path
            )):
                source = SemanticNodeService.leiden_source(
                    projection_id="prac-infra-gov-v1",
                    artifact_source="official",
                    incubator_number=None,
                    language="es",
                )
            self.assertEqual(source["clustering_sha256"], graph_file_sha256(graph_path))
            self.assertEqual(source["communities"], [
                {"community_id": "C001", "member_count": 2},
                {"community_id": "C002", "member_count": 1},
            ])
            with self.assertRaises(SemanticNodeError):
                _read_partition(graph_path, metadata_path, "0" * 64)

    def test_generated_description_rejects_unknown_sentence_without_writing(self):
        member_id = uuid4()
        node = SimpleNamespace(
            id=uuid4(), status="pending_description", projection_id="prac-infra-gov-v1",
            scope_type="corpus", scope_id=None, language="es",
            artifact_source="official",
            clustering_sha256="0" * 64,
            updated_at=datetime.now(timezone.utc),
            members=[SimpleNamespace(canonical_id=member_id)],
            incubator_support=[], document_count=0,
        )
        payload = {
            "title": "Prácticas forestales",
            "description": "Las prácticas forestales aparecen asociadas.",
            "supporting_evidence": [{
                "claim": "Las prácticas forestales aparecen asociadas.",
                "canonical_ids": [str(member_id)],
                "sentence_refs": [{"document_id": str(uuid4()), "sentence_id": "inventada"}],
            }],
            "uncertainties": [],
        }
        response = SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(payload))],
        )
        client = Mock()
        client.messages.create.return_value = response
        db = Mock()
        evidence = {
            "evidence_sentences": [],
            "evidence_coverage": {"selected_edge_count": 0},
        }
        with (
            patch("src.services.semantic_nodes._read_node", return_value=node),
            patch("src.services.semantic_nodes._artifacts", return_value=(Path("graph"), Path("json"))),
            patch("src.services.semantic_nodes._read_partition", return_value=(nx.Graph(), {})),
            patch("src.services.semantic_nodes._support", return_value=([], 0)),
            patch("src.services.semantic_nodes._evidence", return_value=evidence),
            patch("src.services.semantic_nodes.get_anthropic_client", return_value=client),
            patch.object(settings, "SEMANTIC_NODE_PROMPT_PATH", Path("data/prompts/semantic_node_prompt.md")),
        ):
            with self.assertRaises(SemanticNodeError):
                SemanticNodeService.generate(db, node.id)
        db.commit.assert_not_called()
        self.assertEqual(node.status, "pending_description")

    def test_accepted_node_cannot_be_regenerated(self):
        node = SimpleNamespace(status="accepted")
        with patch("src.services.semantic_nodes._read_node", return_value=node):
            with self.assertRaises(SemanticNodeError):
                SemanticNodeService.generate(Mock(), uuid4())

    def test_generation_keeps_prompt_provenance_and_creates_draft(self):
        member_id = uuid4()
        document_id = uuid4()
        node = SimpleNamespace(
            id=uuid4(), status="pending_description", projection_id="prac-infra-gov-v1",
            scope_type="corpus", scope_id=None, language="es",
            artifact_source="official",
            clustering_sha256="0" * 64, updated_at=datetime.now(timezone.utc),
            members=[SimpleNamespace(canonical_id=member_id)],
            incubator_support=[], document_count=0, generation=None,
        )
        payload = {
            "title": "Prácticas forestales comunitarias",
            "description": "Las prácticas forestales aparecen asociadas en la oración.",
            "supporting_evidence": [{
                "claim": "Las prácticas forestales aparecen asociadas.",
                "canonical_ids": [str(member_id)],
                "sentence_refs": [{"document_id": str(document_id), "sentence_id": "s1"}],
            }],
            "uncertainties": [],
        }
        response = SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(payload))],
        )
        client = Mock()
        client.messages.create.return_value = response
        db = Mock()
        evidence = {
            "evidence_sentences": [{
                "document_id": str(document_id), "sentence_id": "s1",
                "canonical_ids": [str(member_id)],
            }],
            "evidence_coverage": {"selected_edge_count": 1},
        }
        with (
            patch("src.services.semantic_nodes._read_node", return_value=node),
            patch("src.services.semantic_nodes._artifacts", return_value=(Path("graph"), Path("json"))),
            patch("src.services.semantic_nodes._read_partition", return_value=(nx.Graph(), {})),
            patch("src.services.semantic_nodes._support", return_value=([], 0)),
            patch("src.services.semantic_nodes._evidence", return_value=evidence),
            patch("src.services.semantic_nodes.get_anthropic_client", return_value=client),
            patch("src.services.semantic_nodes._node_dict", return_value={"id": node.id}),
            patch.object(settings, "SEMANTIC_NODE_PROMPT_PATH", Path("data/prompts/semantic_node_prompt.md")),
        ):
            result = SemanticNodeService.generate(db, node.id)
        self.assertEqual(result["id"], node.id)
        self.assertEqual(node.status, "draft")
        self.assertEqual(node.title, payload["title"])
        self.assertEqual(node.generation["prompt_version"], "semantic-node-v1")
        self.assertEqual(node.generation["supporting_evidence"], payload["supporting_evidence"])
        db.commit.assert_called_once()
