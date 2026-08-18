import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from src.models.canonical_entities import CanonicalEntity
from src.services.fuzzy_matching import (
    RESOLUTION_VERSION,
    asociar_entidades_canonicas,
    canonicalizar_actor_generico,
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
        aliases_read_patcher = patch(
            "src.services.fuzzy_matching.CanonicalEntityAliasRepo.leer_todos",
            return_value=[],
        )
        aliases_register_patcher = patch(
            "src.services.fuzzy_matching.CanonicalEntityAliasRepo.registrar"
        )
        self.aliases_read = aliases_read_patcher.start()
        self.aliases_register = aliases_register_patcher.start()
        self.addCleanup(aliases_register_patcher.stop)
        self.addCleanup(aliases_read_patcher.stop)

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
        self.assertEqual(stats["exact"], 1)
        self.assertEqual(sum(stats.values()), 1)
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

    def test_controlled_singularization_preserves_gender_and_phrase(self) -> None:
        self.assertEqual(canonicalizar_actor_generico("MINEROS"), "minero")
        self.assertEqual(canonicalizar_actor_generico("mineras"), "minera")
        self.assertEqual(canonicalizar_actor_generico("docentes"), "docente")
        self.assertEqual(canonicalizar_actor_generico("presidentes"), "presidente")
        self.assertEqual(
            canonicalizar_actor_generico("mineros artesanales"),
            "minero artesanal",
        )
        self.assertIsNone(
            canonicalizar_actor_generico("Asociación de Pequeños Mineros")
        )
        self.assertIsNone(
            canonicalizar_actor_generico("mineros que abandonaron la minería")
        )
        self.assertIsNone(canonicalizar_actor_generico("varones o mujeres"))

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_generic_actor_variants_converge_without_losing_original_text(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        leer_todas.return_value = []
        created: list[CanonicalEntity] = []

        def create_canonical(_: Mock, canonical_name: str, category: str):
            item = canonical(canonical_name, category)
            created.append(item)
            return item

        crear.side_effect = create_canonical
        inputs = [
            mention("MINEROS", "CHAR"),
            mention("mineros", "CHAR"),
            mention("minero", "CHAR"),
            mention("mineras", "CHAR"),
            mention("minera", "CHAR"),
        ]

        result, stats = asociar_entidades_canonicas(self.db, inputs)

        self.assertEqual(
            [item.canonical_name for item in created], ["minero", "minera"]
        )
        self.assertEqual({item["canonical_id"] for item in result[:3]}, {created[0].id})
        self.assertEqual({item["canonical_id"] for item in result[3:]}, {created[1].id})
        self.assertNotEqual(created[0].id, created[1].id)
        self.assertEqual(
            [item["text"] for item in result], [item["text"] for item in inputs]
        )
        self.assertEqual(stats["morphology"], 3)
        self.assertTrue(
            all(item["resolution_version"] == RESOLUTION_VERSION for item in result)
        )

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_generic_actor_qualifier_remains_a_distinct_identity(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        leer_todas.return_value = []
        created: list[CanonicalEntity] = []

        def create_canonical(_: Mock, canonical_name: str, category: str):
            item = canonical(canonical_name, category)
            created.append(item)
            return item

        crear.side_effect = create_canonical

        result, _ = asociar_entidades_canonicas(
            self.db,
            [mention("mineros", "CHAR"), mention("mineros artesanales", "CHAR")],
        )

        self.assertEqual(
            [item.canonical_name for item in created],
            ["minero", "minero artesanal"],
        )
        self.assertNotEqual(result[0]["canonical_id"], result[1]["canonical_id"])

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_document_person_variants_resolve_to_longest_full_name(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        existing = canonical("Griselda Zubizarreta Vargas", "CHAR")
        leer_todas.return_value = [existing]

        result, stats = asociar_entidades_canonicas(
            self.db,
            [
                mention("Griselda Zubizarreta Vargas", "CHAR"),
                mention("Griselda Zubizarreta", "CHAR"),
                mention("Griselda", "CHAR"),
            ],
        )

        self.assertEqual({item["canonical_id"] for item in result}, {existing.id})
        self.assertEqual(result[0]["match_type"], "exact")
        self.assertEqual(result[1]["match_type"], "person_alias")
        self.assertEqual(result[2]["match_type"], "person_alias")
        self.assertEqual(stats["person_alias"], 2)
        self.assertEqual(
            result[2]["resolution_details"]["rule"],
            "unique_document_name_prefix",
        )
        crear.assert_not_called()

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_bare_first_name_is_not_merged_when_document_has_two_families(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        leer_todas.return_value = []

        def create_canonical(_: Mock, canonical_name: str, category: str):
            return canonical(canonical_name, category)

        crear.side_effect = create_canonical
        result, _ = asociar_entidades_canonicas(
            self.db,
            [
                mention("Griselda Pérez", "CHAR"),
                mention("Griselda Zubizarreta", "CHAR"),
                mention("Griselda", "CHAR"),
            ],
        )

        self.assertEqual(len({item["canonical_id"] for item in result}), 3)
        self.assertEqual(result[2]["match_type"], "new")

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_corporate_suffix_is_not_treated_as_a_person_surname(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        leer_todas.return_value = []

        def create_canonical(_: Mock, canonical_name: str, category: str):
            return canonical(canonical_name, category)

        crear.side_effect = create_canonical
        result, _ = asociar_entidades_canonicas(
            self.db,
            [mention("Conirsa", "CHAR"), mention("Conirsa SA", "CHAR")],
        )

        self.assertEqual(len({item["canonical_id"] for item in result}), 2)
        self.assertNotIn("person_alias", {item["match_type"] for item in result})

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_unique_longer_person_name_can_resolve_two_token_variant(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        existing = canonical("Griselda Zubizarreta Vargas", "CHAR")
        leer_todas.return_value = [existing]

        result, _ = asociar_entidades_canonicas(
            self.db, [mention("Griselda Zubizarreta", "CHAR")]
        )

        self.assertEqual(result[0]["canonical_id"], existing.id)
        self.assertEqual(result[0]["match_type"], "person_name")
        crear.assert_not_called()

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_unique_stored_multiword_alias_is_reused(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        existing = canonical("Griselda Zubizarreta Vargas", "CHAR")
        leer_todas.return_value = [existing]
        self.aliases_read.return_value = [
            SimpleNamespace(
                canonical_id=existing.id,
                normalized_alias=normalizar_nombre("G. Zubizarreta"),
            )
        ]

        result, _ = asociar_entidades_canonicas(
            self.db, [mention("G. Zubizarreta", "CHAR")]
        )

        self.assertEqual(result[0]["canonical_id"], existing.id)
        self.assertEqual(result[0]["match_type"], "stored_alias")
        crear.assert_not_called()

    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.crear")
    @patch("src.services.fuzzy_matching.CanonicalEntityRepo.leer_todas")
    def test_stored_bare_first_name_is_not_reused_without_document_anchor(
        self, leer_todas: Mock, crear: Mock
    ) -> None:
        existing = canonical("Griselda Zubizarreta Vargas", "CHAR")
        new = canonical("Griselda", "CHAR")
        leer_todas.return_value = [existing]
        crear.return_value = new
        self.aliases_read.return_value = [
            SimpleNamespace(
                canonical_id=existing.id,
                normalized_alias=normalizar_nombre("Griselda"),
            )
        ]

        result, _ = asociar_entidades_canonicas(self.db, [mention("Griselda", "CHAR")])

        self.assertEqual(result[0]["canonical_id"], new.id)
        self.assertEqual(result[0]["match_type"], "new")


if __name__ == "__main__":
    unittest.main()
