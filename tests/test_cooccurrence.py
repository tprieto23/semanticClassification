import csv
import tempfile
import unittest
from pathlib import Path

from src.analysis.cooccurrence import (
    MentionRecord,
    build_sentence_cooccurrence,
    export_result,
    validate_json_against_db,
)


def mention(
    canonical_id: str,
    canonical_name: str,
    category: str,
    sentence_id: str,
    start: int,
    *,
    text: str | None = None,
    ambiguity: str = "low",
) -> MentionRecord:
    literal = text or canonical_name
    return MentionRecord(
        document_id="00000000-0000-0000-0000-000000000001",
        sentence_id=sentence_id,
        canonical_id=canonical_id,
        canonical_name=canonical_name,
        category=category,
        text=literal,
        start=start,
        end=start + len(literal),
        context=f"Contexto de {sentence_id}",
        ambiguity=ambiguity,
    )


def read_matrix_market(path: Path):
    with path.open(encoding="utf-8") as file:
        data_lines = [line.strip() for line in file if not line.startswith("%")]
    rows, columns, nonzero = map(int, data_lines[0].split())
    entries = [tuple(map(int, line.split())) for line in data_lines[1:]]
    return rows, columns, nonzero, entries


class SentenceCooccurrenceTests(unittest.TestCase):
    def test_repeated_node_in_one_sentence_counts_once(self) -> None:
        mentions = [
            mention("a", "Mineros", "CHAR", "s-1", 0),
            mention("a", "Mineros", "CHAR", "s-1", 20),
            mention("b", "Minería artesanal", "PRAC", "s-1", 40),
        ]

        result = build_sentence_cooccurrence(mentions)

        self.assertEqual(len(result.incidence_entries), 2)
        self.assertEqual(list(result.edge_weights.values()), [1])
        self.assertEqual(len(result.observations), 1)
        observation = result.observations[0]
        self.assertEqual(
            sorted(
                (observation.source_mention_count, observation.target_mention_count)
            ),
            [1, 2],
        )

    def test_same_pair_in_two_sentences_has_weight_two(self) -> None:
        mentions = [
            mention("a", "Mineros", "CHAR", "s-1", 0),
            mention("b", "Minería artesanal", "PRAC", "s-1", 20),
            mention("a", "Mineros", "CHAR", "s-2", 100),
            mention("b", "Minería artesanal", "PRAC", "s-2", 120),
        ]

        result = build_sentence_cooccurrence(mentions)

        self.assertEqual(list(result.edge_weights.values()), [2])
        self.assertEqual(len(result.observations), 2)

    def test_only_repeated_node_does_not_create_self_loop(self) -> None:
        result = build_sentence_cooccurrence(
            [
                mention("a", "Mineros", "CHAR", "s-1", 0),
                mention("a", "Mineros", "CHAR", "s-1", 20),
            ]
        )

        self.assertEqual(result.edge_weights, {})
        self.assertEqual(len(result.incidence_entries), 1)

    def test_same_canonical_id_cannot_change_category(self) -> None:
        with self.assertRaises(ValueError):
            build_sentence_cooccurrence(
                [
                    mention("a", "Entidad", "CHAR", "s-1", 0),
                    mention("a", "Entidad", "LOC", "s-2", 20),
                ]
            )

    def test_exported_adjacency_is_symmetric_and_has_zero_diagonal(self) -> None:
        mentions = [
            mention("a", "Mineros", "CHAR", "s-1", 0),
            mention("b", "Minería artesanal", "PRAC", "s-1", 20),
            mention("c", "Madre de Dios", "LOC", "s-1", 50),
        ]
        result = build_sentence_cooccurrence(mentions)

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            export_result(
                result,
                output_dir,
                document_id=mentions[0].document_id,
                ner_json_path=Path("example.json"),
                json_mention_count=len(mentions),
            )
            rows, columns, nonzero, entries = read_matrix_market(
                output_dir / "cooccurrence_adjacency.mtx"
            )

        self.assertEqual((rows, columns), (3, 3))
        self.assertEqual(nonzero, 6)
        values = {(row, column): value for row, column, value in entries}
        self.assertFalse(any(row == column for row, column in values))
        for (row, column), value in values.items():
            self.assertEqual(values[(column, row)], value)

    def test_category_summary_preserves_all_flat_categories(self) -> None:
        mentions = [
            mention("c1", "Actores", "CHAR", "s-1", 60),
            mention("c2", "Organizaciones", "CHAR", "s-1", 80),
            mention("l1", "Río", "LOC", "s-1", 100),
            mention("l2", "Territorio", "LOC", "s-1", 120),
            mention("p", "Minería", "PRAC", "s-1", 0),
            mention("i", "Draga", "INFRA", "s-1", 20),
            mention("g", "Ley minera", "GOV", "s-1", 40),
        ]
        result = build_sentence_cooccurrence(mentions)

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            export_result(
                result,
                output_dir,
                document_id=mentions[0].document_id,
                ner_json_path=Path("example.json"),
                json_mention_count=len(mentions),
            )
            with (output_dir / "category_pair_summary.csv").open(
                encoding="utf-8"
            ) as file:
                rows = list(csv.DictReader(file))

        observed = {
            (row["source_category"], row["target_category"]): int(row["observed_edges"])
            for row in rows
        }
        self.assertEqual(observed[("PRAC", "INFRA")], 1)
        self.assertEqual(observed[("PRAC", "GOV")], 1)
        self.assertEqual(observed[("INFRA", "GOV")], 1)
        self.assertEqual(observed[("CHAR", "CHAR")], 1)
        self.assertEqual(observed[("LOC", "LOC")], 1)

    def test_semantic_projection_builds_all_six_pairs_and_preserves_context(self) -> None:
        mentions = [
            mention("p1", "Práctica uno", "PRAC", "s-1", 0),
            mention("p2", "Práctica dos", "PRAC", "s-1", 20),
            mention("i1", "Infraestructura uno", "INFRA", "s-1", 40),
            mention("i2", "Infraestructura dos", "INFRA", "s-1", 60),
            mention("g1", "Gobernanza uno", "GOV", "s-1", 80),
            mention("g2", "Gobernanza dos", "GOV", "s-1", 100),
            mention("c1", "Actor contextual", "CHAR", "s-1", 120),
            mention("l1", "Lugar contextual", "LOC", "s-1", 140),
        ]

        result = build_sentence_cooccurrence(
            mentions,
            node_categories=("PRAC", "INFRA", "GOV"),
        )

        self.assertEqual(len(result.nodes), 6)
        self.assertEqual(len(result.edge_weights), 15)
        self.assertEqual(
            {"--".join(pair) for pair in result.allowed_category_pairs},
            {
                "PRAC--PRAC",
                "PRAC--INFRA",
                "PRAC--GOV",
                "INFRA--INFRA",
                "INFRA--GOV",
                "GOV--GOV",
            },
        )
        self.assertEqual(
            {entity.category for entity in result.sentence_entities},
            {"CHAR", "LOC", "PRAC", "INFRA", "GOV"},
        )
        self.assertEqual(
            {
                entity.category
                for entity in result.sentence_entities
                if not entity.is_projected
            },
            {"CHAR", "LOC"},
        )
        self.assertTrue(
            all(
                result.nodes[source].category not in {"CHAR", "LOC"}
                and result.nodes[target].category not in {"CHAR", "LOC"}
                for source, target in result.edge_weights
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            export_result(result, output_dir, document_id=mentions[0].document_id)
            with (output_dir / "category_pair_summary.csv").open(
                encoding="utf-8"
            ) as file:
                pair_rows = list(csv.DictReader(file))
            with (output_dir / "sentence_entities.csv").open(
                encoding="utf-8"
            ) as file:
                entity_rows = list(csv.DictReader(file))
            with (output_dir / "edge_observations.csv").open(
                encoding="utf-8"
            ) as file:
                evidence_rows = list(csv.DictReader(file))

        self.assertEqual(len(pair_rows), 6)
        self.assertEqual(len(entity_rows), 8)
        self.assertEqual(len(evidence_rows), 15)
        self.assertTrue(all(row["category_pair"] for row in evidence_rows))
        self.assertTrue(all("pair_context" in row for row in evidence_rows))

    def test_projection_can_select_only_one_category_pair(self) -> None:
        result = build_sentence_cooccurrence(
            [
                mention("p", "Práctica", "PRAC", "s-1", 0),
                mention("i", "Infraestructura", "INFRA", "s-1", 20),
                mention("g", "Gobernanza", "GOV", "s-1", 40),
            ],
            node_categories=("PRAC", "GOV"),
            allowed_category_pairs=(("PRAC", "GOV"),),
        )

        self.assertEqual({node.category for node in result.nodes}, {"PRAC", "GOV"})
        self.assertEqual(len(result.edge_weights), 1)
        self.assertEqual(result.allowed_category_pairs, (("PRAC", "GOV"),))

        with self.assertRaisesRegex(ValueError, "fuera de node_categories"):
            build_sentence_cooccurrence(
                [mention("p", "Práctica", "PRAC", "s-1", 0)],
                node_categories=("PRAC",),
                allowed_category_pairs=(("PRAC", "GOV"),),
            )

    def test_different_contexts_in_one_sentence_are_preserved_per_edge(self) -> None:
        first = mention("a", "Actores", "CHAR", "s-1", 0)
        second = mention("b", "Territorio", "LOC", "s-1", 20)
        first = MentionRecord(**{**first.__dict__, "context": "Contexto de actores"})
        second = MentionRecord(
            **{**second.__dict__, "context": "Contexto del territorio"}
        )

        result = build_sentence_cooccurrence([first, second])

        self.assertEqual(len(result.observations), 1)
        self.assertIn("Contexto de actores", result.observations[0].context)
        self.assertIn("Contexto del territorio", result.observations[0].context)

    def test_json_database_validation_detects_differences(self) -> None:
        db_mention = mention("a", "Mineros", "CHAR", "s-1", 0)
        json_entity = {
            "text": db_mention.text,
            "category": db_mention.category,
            "start": db_mention.start,
            "end": db_mention.end,
            "sentence_id": db_mention.sentence_id,
            "context": db_mention.context,
            "ambiguity": db_mention.ambiguity,
        }
        validate_json_against_db([json_entity], [db_mention])

        json_entity["text"] = "Otro texto"
        with self.assertRaises(ValueError):
            validate_json_against_db([json_entity], [db_mention])


if __name__ == "__main__":
    unittest.main()
