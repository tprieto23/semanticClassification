import os
import sys
import types
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

if "anthropic" not in sys.modules:
    anthropic_stub = types.ModuleType("anthropic")
    anthropic_stub.Anthropic = type("Anthropic", (), {})
    sys.modules["anthropic"] = anthropic_stub

from src.services.ner import _parsear_datos, _segmentar_oraciones


class NerMentionPositionTests(unittest.TestCase):
    def test_annotations_out_of_order_keep_document_positions(self) -> None:
        text = "La minería afectó el río.\n\n" "Las comunidades rechazaron la minería."
        sentences = _segmentar_oraciones(text, 0)
        first_id = sentences[0]["sentence_id"]
        second_id = sentences[1]["sentence_id"]
        response = {
            "annotations": [
                {
                    "sentence_id": second_id,
                    "label": "PRAC",
                    "text": "minería",
                    "ambiguity": "low",
                },
                {
                    "sentence_id": first_id,
                    "label": "LOC",
                    "text": "río",
                    "ambiguity": "low",
                },
                {
                    "sentence_id": first_id,
                    "label": "PRAC",
                    "text": "minería",
                    "ambiguity": "low",
                },
                {
                    "sentence_id": second_id,
                    "label": "CHAR",
                    "text": "comunidades",
                    "ambiguity": "low",
                },
            ]
        }

        entities = _parsear_datos(response, sentences)

        self.assertEqual(
            [entity["text"] for entity in entities],
            ["minería", "río", "comunidades", "minería"],
        )
        for entity in entities:
            self.assertEqual(text[entity["start"] : entity["end"]], entity["text"])

    def test_repeated_span_in_one_sentence_uses_each_occurrence(self) -> None:
        text = "minería y minería."
        sentences = _segmentar_oraciones(text, 0)
        sentence_id = sentences[0]["sentence_id"]
        annotation = {
            "sentence_id": sentence_id,
            "label": "PRAC",
            "text": "minería",
            "ambiguity": "low",
        }

        entities = _parsear_datos(
            {"annotations": [annotation, annotation.copy()]}, sentences
        )

        self.assertEqual(
            [(entity["start"], entity["end"]) for entity in entities],
            [(0, 7), (10, 17)],
        )

    def test_case_variants_are_distinct_mentions(self) -> None:
        text = "Minería y minería."
        sentences = _segmentar_oraciones(text, 0)
        sentence_id = sentences[0]["sentence_id"]
        response = {
            "annotations": [
                {
                    "sentence_id": sentence_id,
                    "label": "PRAC",
                    "text": "minería",
                    "ambiguity": "low",
                },
                {
                    "sentence_id": sentence_id,
                    "label": "PRAC",
                    "text": "Minería",
                    "ambiguity": "low",
                },
            ]
        }

        entities = _parsear_datos(response, sentences)

        self.assertEqual(
            [entity["text"] for entity in entities], ["Minería", "minería"]
        )
        self.assertEqual(
            [(entity["start"], entity["end"]) for entity in entities],
            [(0, 7), (10, 17)],
        )


if __name__ == "__main__":
    unittest.main()
