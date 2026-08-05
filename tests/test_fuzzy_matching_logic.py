import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from src.models.canonical_entities import CanonicalEntity
from src.services.fuzzy_matching import (
    asociar_entidades_canonicas,
    normalizar_nombre,
)


def canonical(name: str, category: str) -> CanonicalEntity:
    return CanonicalEntity(id=uuid4(), canonical_name=name, category=category)


def mention(text: str, category: str) -> dict:
    return {
        "text": text,
        "category": category,
        "start": 0,
        "end": len(text),
        "sentence_id": "s-000000000",
        "context": text,
        "ambiguity": "low",
    }


class FuzzyMatchingLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Mock()

    def test_normalization_ignores_case_accents_and_repeated_spaces(self) -> None:
        self.assertEqual(
            normalizar_nombre("  RÍO   Madre de Dios "),
            "rio madre de dios",
        )

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_exact_normalized_match_reuses_canonical(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        existing = canonical("Madre de Dios", "LOC")
        leer_todas.return_value = [existing]

        result, stats = asociar_entidades_canonicas(
            self.db, [mention("MADRE DE DIÓS", "LOC")]
        )

        self.assertEqual(result[0]["canonical_id"], existing.id)
        self.assertEqual(result[0]["match_type"], "exact")
        self.assertEqual(stats, {"exact": 1, "fuzzy": 0, "new": 0})
        crear.assert_not_called()

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_candidates_from_other_categories_are_not_reused(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        leer_todas.return_value = [canonical("Madre de Dios", "CHAR")]
        new = canonical("Madre de Dios", "LOC")
        crear.return_value = new

        result, _ = asociar_entidades_canonicas(
            self.db, [mention("Madre de Dios", "LOC")]
        )

        self.assertEqual(result[0]["canonical_id"], new.id)
        self.assertEqual(result[0]["match_type"], "new")

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_strong_fuzzy_match_reuses_clear_candidate(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        existing = canonical("Puerto Maldonado", "LOC")
        leer_todas.return_value = [existing]

        result, _ = asociar_entidades_canonicas(
            self.db, [mention("Puerto Maldonadoo", "LOC")]
        )

        self.assertEqual(result[0]["canonical_id"], existing.id)
        self.assertEqual(result[0]["match_type"], "fuzzy")
        crear.assert_not_called()

    @patch("src.services.fuzzy_matching._puntaje", side_effect=[97.0, 95.0])
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_close_second_candidate_prevents_automatic_merge(
        self, leer_todas: Mock, crear: Mock, _puntaje: Mock
    ) -> None:
        leer_todas.return_value = [
            canonical("Ministerio del Ambiente", "GOV"),
            canonical("Ministerio de Ambiente", "GOV"),
        ]
        new = canonical("Ministerio Ambiente", "GOV")
        crear.return_value = new

        result, _ = asociar_entidades_canonicas(
            self.db, [mention("Ministerio Ambiente", "GOV")]
        )

        self.assertEqual(result[0]["canonical_id"], new.id)
        self.assertEqual(result[0]["match_type"], "new")

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_short_terms_require_exact_match(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        leer_todas.return_value = [canonical("Oro", "PRAC")]
        new = canonical("Ora", "PRAC")
        crear.return_value = new

        result, _ = asociar_entidades_canonicas(self.db, [mention("Ora", "PRAC")])

        self.assertEqual(result[0]["canonical_id"], new.id)
        self.assertEqual(result[0]["match_type"], "new")


if __name__ == "__main__":
    unittest.main()
