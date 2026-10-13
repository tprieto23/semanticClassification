"""Regresiones del contrato de diez categorías, sin proveedor ni DB reales."""

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "semantic-mpl"))

if "anthropic" not in sys.modules:
    anthropic_stub = types.ModuleType("anthropic")
    anthropic_stub.Anthropic = type("Anthropic", (), {})
    sys.modules["anthropic"] = anthropic_stub

from src.analysis.cooccurrence import MentionRecord, build_sentence_cooccurrence, export_result
from src.analysis.network_visualization import load_core_network
from src.categories import ACTIVE_CATEGORIES
from src.models.canonical_entities import CanonicalEntity
from src.models.documents import Document  # noqa: F401 — registro del mapper SQLAlchemy
from src.models.entities_repo import EntityRepo
from src.services import ner
from src.services.fuzzy_matching import asociar_entidades_canonicas


EXPECTED_CATEGORIES = {
    "CHAR", "KNOW", "ATT", "SKILL", "PRAC", "physical_INFRA",
    "soft_INFRA", "eco_INFRA", "RUL", "LOC",
}


def create_canonical(db, canonical_name, category):
    return CanonicalEntity(id=uuid4(), canonical_name=canonical_name, category=category)


class CategoryPipelineTests(unittest.TestCase):
    def test_ten_categories_survive_request_resolution_and_persistence(self):
        payload = json.loads(Path("data/ner/few_shot_examples.json").read_text())
        examples = {example["text"]: example for example in payload["examples"]}
        document_text = "\n\n".join(examples)
        client = Mock()

        def respond(**request):
            schema = request["tools"][0]["input_schema"]
            labels = schema["properties"]["annotations"]["items"]["properties"]["label"]["enum"]
            self.assertEqual(set(labels), EXPECTED_CATEGORIES)
            for label in EXPECTED_CATEGORIES:
                self.assertIn(f"`{label}`:", request["system"])
            input_text = request["messages"][0]["content"].split("<target_input>")[1]
            input_data = json.loads(input_text.split("</target_input>")[0])
            annotations = [
                {**annotation, "sentence_id": sentence["sentence_id"]}
                for sentence in input_data["sentences"]
                for annotation in examples[sentence["text"]]["annotations"]
            ]
            return SimpleNamespace(
                stop_reason="tool_use",
                content=[SimpleNamespace(
                    type="tool_use", name=ner.NER_TOOL_NAME,
                    input={"document_id": input_data["document_id"], "annotations": annotations},
                )],
            )

        client.messages.create.side_effect = respond
        with (
            patch.object(ner, "get_anthropic_client", return_value=client),
            patch.object(ner, "_SYSTEM_PROMPT", None),
            patch.object(ner, "_FEW_SHOT_EXAMPLES", None),
        ):
            mentions = ner.extraer_entidades(document_text, document_id="test-document")

        self.assertEqual(ACTIVE_CATEGORIES, EXPECTED_CATEGORIES)
        self.assertEqual({mention["category"] for mention in mentions}, EXPECTED_CATEGORIES)
        self.assertEqual(len(mentions), sum(len(e["annotations"]) for e in examples.values()))
        for mention in mentions:
            self.assertEqual(document_text[mention["start"]:mention["end"]], mention["text"])

        db = Mock()
        with (
            patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas", return_value=[]),
            patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear", side_effect=create_canonical),
            patch("src.services.fuzzy_matching.CanonicalEntityAliasRepo.leer_todos", return_value=[]),
            patch("src.services.fuzzy_matching.CanonicalEntityAliasRepo.registrar"),
        ):
            resolved, _ = asociar_entidades_canonicas(db, mentions)

        EntityRepo.reemplazar_entidades(db, uuid4(), resolved)
        stored = [call.args[0] for call in db.add.call_args_list]
        self.assertEqual(len(stored), len(mentions))
        self.assertEqual({entity.category for entity in stored}, EXPECTED_CATEGORIES)
        self.assertTrue(all(entity.canonical_id for entity in stored))

    def test_flat_graph_and_visualization_preserve_all_ten_categories(self):
        mentions = [
            MentionRecord(
                document_id="document", sentence_id="s-1", canonical_id=label,
                canonical_name=label, category=label, text=label,
                start=index * 30, end=index * 30 + len(label), context="Evidencia común",
                ambiguity="low",
            )
            for index, label in enumerate(sorted(EXPECTED_CATEGORIES))
        ]
        result = build_sentence_cooccurrence(mentions)
        self.assertEqual(set(result.node_categories), EXPECTED_CATEGORIES)
        self.assertEqual(len(result.allowed_category_pairs), 55)
        self.assertEqual(len(result.nodes), 10)
        self.assertEqual(len(result.edge_weights), 45)
        with tempfile.TemporaryDirectory() as directory:
            export_result(result, Path(directory), scope="test:ten-categories")
            data = load_core_network(Path(directory), minimum_weight=1, include_isolates=True)
            self.assertEqual({node["category"] for _, node in data.graph.nodes(data=True)}, EXPECTED_CATEGORIES)
            self.assertEqual(data.graph.number_of_edges(), 45)

    def test_legacy_infra_is_rejected_by_ner_and_kept_separate_in_resolution(self):
        sentences = ner._segmentar_oraciones("sistema de monitoreo", 0)
        annotations = [{
            "label": "INFRA", "text": "sistema de monitoreo",
            "sentence_id": sentences[0]["sentence_id"], "ambiguity": "low",
        }]
        self.assertEqual(ner._parsear_datos({"annotations": annotations}, sentences), [])
        old = create_canonical(None, "sistema de monitoreo", "INFRA")
        mentions = [
            {"category": category, "text": "sistema de monitoreo", "start": 0, "end": 20}
            for category in ("INFRA", "soft_INFRA")
        ]
        with (
            patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas", return_value=[old]),
            patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear", side_effect=create_canonical),
            patch("src.services.fuzzy_matching.CanonicalEntityAliasRepo.leer_todos", return_value=[]),
            patch("src.services.fuzzy_matching.CanonicalEntityAliasRepo.registrar"),
        ):
            resolved, _ = asociar_entidades_canonicas(Mock(), mentions)
        self.assertEqual(resolved[0]["canonical_id"], old.id)
        self.assertNotEqual(resolved[1]["canonical_id"], old.id)
        self.assertEqual([m["category"] for m in resolved], ["INFRA", "soft_INFRA"])


if __name__ == "__main__":
    unittest.main()
