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
    def test_missing_or_empty_codebook_fails_before_contacting_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.md"
            empty = Path(directory) / "empty.md"
            empty.write_text(" \n", encoding="utf-8")
            for path, error in [(missing, FileNotFoundError), (empty, ValueError)]:
                with self.subTest(path=path.name):
                    with (
                        patch.object(ner.settings, "NER_CODEBOOK_PATH", path),
                        patch.object(ner, "_PROMPT_RESOURCES", None),
                        patch.object(ner, "get_anthropic_client") as provider,
                    ):
                        with self.assertRaises(error):
                            ner.extraer_entidades("Las agricultoras participan.", "document")
                        provider.assert_not_called()

    def test_codebook_template_markers_are_preserved_as_literal_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "codebook.md"
            content = "# Specification\n\nThe service uses `$codebook` and `$json_input`.\n"
            path.write_text(content, encoding="utf-8")
            with (
                patch.object(ner.settings, "NER_CODEBOOK_PATH", path),
                patch.object(ner, "_PROMPT_RESOURCES", None),
            ):
                self.assertIn(content, ner._build_prompt("{}"))

    def test_ten_categories_survive_request_resolution_and_persistence(self):
        # Datos del proveedor simulado: no se incorporan a los prompts.
        fixtures = [
            ("CHAR", "Las agricultoras participan.", "agricultoras"),
            ("KNOW", "Conocen los ciclos de floración.", "ciclos de floración"),
            ("ATT", "Expresan compromiso con el bosque.", "compromiso con el bosque"),
            ("SKILL", "Tienen capacidad para monitorear.", "capacidad para monitorear"),
            ("PRAC", "Se realiza restauración forestal.", "restauración forestal"),
            ("physical_INFRA", "El puente conecta las localidades.", "puente"),
            ("soft_INFRA", "El vivero produce plantas.", "vivero"),
            ("eco_INFRA", "Los humedales regulan el agua.", "humedales"),
            ("RUL", "El reglamento establece obligaciones.", "reglamento"),
            ("LOC", "El taller se realizó en Tambopata.", "Tambopata"),
        ]
        by_sentence = {sentence: {"label": label, "text": span, "ambiguity": "low"}
                       for label, sentence, span in fixtures}
        document_text = "\n\n".join(by_sentence)
        codebook = Path(ner.settings.NER_CODEBOOK_PATH).read_text(encoding="utf-8")
        client = Mock()

        def respond(**request):
            schema = request["tools"][0]["input_schema"]
            labels = schema["properties"]["annotations"]["items"]["properties"]["label"]["enum"]
            self.assertEqual(set(labels), EXPECTED_CATEGORIES)
            self.assertNotIn("system", request)
            self.assertEqual(len(request["messages"]), 1)
            prompt = request["messages"][0]["content"]
            self.assertIn(codebook, prompt)
            self.assertNotIn("<few_shot_examples>", prompt)
            self.assertNotIn("expected_output", prompt)
            for label in EXPECTED_CATEGORIES:
                self.assertIn(f"| {label} |", prompt)
            input_text = prompt.split("<target_input>")[1]
            input_data = json.loads(input_text.split("</target_input>")[0])
            annotations = [
                {**by_sentence[sentence["text"]], "sentence_id": sentence["sentence_id"]}
                for sentence in input_data["sentences"]
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
            patch.object(ner, "_PROMPT_RESOURCES", None),
        ):
            mentions = ner.extraer_entidades(document_text, document_id="test-document")

        self.assertEqual(ACTIVE_CATEGORIES, EXPECTED_CATEGORIES)
        self.assertEqual({mention["category"] for mention in mentions}, EXPECTED_CATEGORIES)
        self.assertEqual(len(mentions), len(fixtures))
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
