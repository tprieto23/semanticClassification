import json
import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

if "anthropic" not in sys.modules:
    anthropic_stub = types.ModuleType("anthropic")
    anthropic_stub.Anthropic = type("Anthropic", (), {})
    sys.modules["anthropic"] = anthropic_stub

if "src.services.pdf_converter" not in sys.modules:
    pdf_converter_stub = types.ModuleType("src.services.pdf_converter")
    pdf_converter_stub.PdfConverter = type("PdfConverter", (), {})
    sys.modules["src.services.pdf_converter"] = pdf_converter_stub

from src.services.documents import DocumentService, DocumentoError


class FuzzyMatchingPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Mock()
        self.document_id = "9b17bd36-b502-497f-8e9d-412c480f0424"

    @patch("src.services.documents.EntityRepo.reemplazar_entidades")
    @patch("src.services.documents.asociar_entidades_canonicas")
    @patch("src.services.documents.Storage.leer")
    @patch("src.services.documents.DocumentRepo.leer_uno")
    def test_reads_ner_json_and_changes_status(
        self,
        leer_uno: Mock,
        leer: Mock,
        asociar: Mock,
        reemplazar: Mock,
    ) -> None:
        doc = SimpleNamespace(
            id=self.document_id,
            status="ner",
            ner_path="s3/archivosNER/doc.json",
        )
        entities = [
            {
                "text": "Madre de Dios",
                "category": "LOC",
                "start": 10,
                "end": 23,
                "sentence_id": "s-000000010",
                "context": None,
                "ambiguity": "low",
            }
        ]
        leer_uno.return_value = doc
        leer.return_value = json.dumps(
            {"document_id": self.document_id, "entities": entities}
        )
        matched_entities = [{**entities[0], "canonical_id": "canonical-id"}]
        asociar.return_value = (
            matched_entities,
            {"exact": 0, "fuzzy": 0, "new": 1},
        )

        result = DocumentService.preparar_fuzzy_matching(self.db, self.document_id)

        self.assertEqual(result, matched_entities)
        leer.assert_called_once_with(doc.ner_path)
        reemplazar.assert_called_once_with(self.db, doc.id, matched_entities)
        self.assertEqual(doc.status, "fuzzyMatching")
        self.db.commit.assert_called_once_with()

    @patch("src.services.documents.DocumentRepo.leer_uno")
    def test_requires_ner_status(self, leer_uno: Mock) -> None:
        leer_uno.return_value = SimpleNamespace(
            status="cleaned", ner_path="s3/archivosNER/doc.json"
        )

        with self.assertRaises(DocumentoError) as raised:
            DocumentService.preparar_fuzzy_matching(self.db, self.document_id)

        self.assertEqual(raised.exception.codigo_http, 409)

    @patch("src.services.documents.DocumentRepo.leer_uno")
    def test_requires_ner_path(self, leer_uno: Mock) -> None:
        leer_uno.return_value = SimpleNamespace(status="ner", ner_path=None)

        with self.assertRaises(DocumentoError) as raised:
            DocumentService.preparar_fuzzy_matching(self.db, self.document_id)

        self.assertEqual(raised.exception.codigo_http, 409)

    @patch("src.services.documents.asociar_entidades_canonicas")
    @patch("src.services.documents.Storage.leer")
    @patch("src.services.documents.DocumentRepo.leer_uno")
    def test_does_not_change_status_for_invalid_json(
        self, leer_uno: Mock, leer: Mock, asociar: Mock
    ) -> None:
        leer_uno.return_value = SimpleNamespace(
            status="ner", ner_path="s3/archivosNER/doc.json"
        )
        leer.return_value = "{invalid"

        with self.assertRaises(DocumentoError) as raised:
            DocumentService.preparar_fuzzy_matching(self.db, self.document_id)

        self.assertEqual(raised.exception.codigo_http, 500)
        asociar.assert_not_called()
        self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
