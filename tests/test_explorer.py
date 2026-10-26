import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

if "src.services.pdf_converter" not in sys.modules:
    pdf_converter_stub = types.ModuleType("src.services.pdf_converter")
    pdf_converter_stub.PdfConverter = type("PdfConverter", (), {})
    sys.modules["src.services.pdf_converter"] = pdf_converter_stub

from pydantic import ValidationError

from src.analysis.cooccurrence import MentionRecord, load_db_mentions
from src.analysis.explorer import (
    ExplorerFilterError,
    ExplorerFilters,
    build_explorer_network,
    compare_rankings,
    resolve_category_pairs,
)
from src.api.main import app
from src.api.routers.explorer import _scope, explorer_network
from src.api.schemas.explorer import (
    ExplorerCompareRequest,
    ExplorerCompareResponse,
    ExplorerNetworkRequest,
    ExplorerNetworkResponse,
)
from src.services.explorer import (
    ExplorerFiltroInvalido,
    ExplorerScope,
    ExplorerService,
    _scoped_documents,
)

DOC_A = "00000000-0000-0000-0000-00000000000a"
DOC_B = "00000000-0000-0000-0000-00000000000b"
DOC_C = "00000000-0000-0000-0000-00000000000c"

ENTITIES = {
    "coop": ("cooperativa", "CHAR"),
    "minero": ("minero", "CHAR"),
    "podas": ("podas", "PRAC"),
    "vivero": ("vivero", "soft_INFRA"),
    "plan": ("plan de manejo", "RUL"),
    "rio": ("río Madre de Dios", "LOC"),
    "carretera": ("carretera", "INFRA"),
}


def _sentences(*sentences: tuple[str, str, tuple[str, ...]]) -> list[MentionRecord]:
    """Crea menciones a partir de (documento, oración, entidades)."""

    mentions = []
    for document_id, sentence_id, entity_keys in sentences:
        for offset, key in enumerate(entity_keys):
            name, category = ENTITIES[key]
            mentions.append(
                MentionRecord(
                    document_id=document_id,
                    sentence_id=sentence_id,
                    canonical_id=key,
                    canonical_name=name,
                    category=category,
                    text=name,
                    start=offset * 100,
                    end=offset * 100 + len(name),
                    context=f"{sentence_id} en {document_id}",
                    ambiguity="low",
                )
            )
    return mentions


CORPUS = _sentences(
    (DOC_A, "s1", ("coop", "podas", "vivero")),
    (DOC_A, "s2", ("coop", "plan")),
    (DOC_A, "s3", ("rio", "podas")),
    (DOC_B, "s1", ("coop", "podas", "plan")),
    (DOC_B, "s2", ("vivero", "rio")),
    (DOC_B, "s3", ("minero", "coop")),
    (DOC_C, "s1", ("podas", "rio")),
)


def _node_ids(network: dict) -> set[str]:
    return {node["id"] for node in network["nodes"]}


def _pairs(network: dict) -> set[str]:
    return {edge["category_pair"] for edge in network["edges"]}


class ExplorerNetworkTests(unittest.TestCase):
    def test_default_links_all_ten_categories_and_counts_every_stage(self) -> None:
        network = build_explorer_network(
            CORPUS, ExplorerFilters(minimum_node_document_count=1, top_n=None)
        )

        self.assertIn("KNOW", network["stages"]["categories"])
        self.assertEqual(len(network["stages"]["categories"]), 10)
        self.assertEqual(
            _node_ids(network), {"coop", "minero", "podas", "vivero", "plan", "rio"}
        )
        self.assertEqual(network["stages"]["mentions"], len(CORPUS))
        self.assertEqual(network["stages"]["shown"]["nodes"], 6)

    def test_legacy_categories_join_only_when_present(self) -> None:
        with_legacy = CORPUS + _sentences((DOC_A, "s9", ("carretera", "podas")))

        self.assertNotIn(
            "INFRA",
            build_explorer_network(CORPUS, ExplorerFilters())["stages"]["categories"],
        )
        network = build_explorer_network(
            with_legacy, ExplorerFilters(minimum_node_document_count=1)
        )
        self.assertIn("INFRA", network["stages"]["categories"])
        self.assertIn("carretera", _node_ids(network))

    def test_link_modes_restrict_category_pairs(self) -> None:
        between = build_explorer_network(
            CORPUS,
            ExplorerFilters(
                categories=("CHAR", "PRAC"),
                link_mode="between",
                minimum_node_document_count=1,
            ),
        )
        within = build_explorer_network(
            CORPUS,
            ExplorerFilters(
                categories=("CHAR",), link_mode="within", minimum_node_document_count=1
            ),
        )
        pairs = build_explorer_network(
            CORPUS,
            ExplorerFilters(
                categories=("CHAR", "PRAC", "RUL"),
                link_mode="pairs",
                category_pairs=(("RUL", "CHAR"),),
                minimum_node_document_count=1,
            ),
        )

        self.assertEqual(_pairs(between), {"CHAR--PRAC"})
        self.assertEqual(_pairs(within), {"CHAR--CHAR"})
        self.assertEqual(_node_ids(within), {"coop", "minero"})
        self.assertEqual(_pairs(pairs), {"CHAR--RUL"})
        self.assertEqual(_node_ids(pairs), {"coop", "plan"})

    def test_invalid_link_combinations_fail_explicitly(self) -> None:
        with self.assertRaisesRegex(ExplorerFilterError, "between"):
            resolve_category_pairs(("CHAR",), "between")
        with self.assertRaisesRegex(ExplorerFilterError, "no seleccionadas"):
            resolve_category_pairs(("CHAR",), "pairs", (("CHAR", "LOC"),))
        with self.assertRaisesRegex(ExplorerFilterError, "requiere"):
            resolve_category_pairs(("CHAR",), "pairs", None)
        with self.assertRaisesRegex(ExplorerFilterError, "no permitidas"):
            build_explorer_network(CORPUS, ExplorerFilters(categories=("GOV",)))

    def test_document_recurrence_removes_single_document_entities(self) -> None:
        network = build_explorer_network(
            CORPUS, ExplorerFilters(minimum_node_document_count=2, top_n=None)
        )

        # minero solo aparece en DOC_B.
        self.assertNotIn("minero", _node_ids(network))
        self.assertEqual(network["stages"]["cooccurrence"]["nodes"], 6)
        self.assertEqual(network["stages"]["document_recurrence"]["nodes"], 5)

    def test_minimum_edge_weight_drops_weak_links_and_orphans(self) -> None:
        network = build_explorer_network(
            CORPUS,
            ExplorerFilters(
                minimum_node_document_count=1,
                edge_weighting="sentence-count",
                minimum_edge_weight=2,
                top_n=None,
            ),
        )

        self.assertTrue(all(edge["sentence_count"] >= 2 for edge in network["edges"]))
        self.assertEqual(
            {(edge["source"], edge["target"]) for edge in network["edges"]},
            {("coop", "podas"), ("coop", "plan"), ("podas", "rio")},
        )
        self.assertNotIn("minero", _node_ids(network))

    def test_metrics_are_ranked_on_full_network_before_top_n(self) -> None:
        full = build_explorer_network(
            CORPUS, ExplorerFilters(minimum_node_document_count=1, top_n=None)
        )
        top_two = build_explorer_network(
            CORPUS, ExplorerFilters(minimum_node_document_count=1, top_n=2)
        )

        full_by_id = {node["id"]: node for node in full["nodes"]}
        self.assertEqual(len(top_two["nodes"]), 2)
        self.assertEqual(
            [node["ranks"]["pagerank"] for node in top_two["nodes"]], [1, 2]
        )
        for node in top_two["nodes"]:
            self.assertEqual(node["metrics"], full_by_id[node["id"]]["metrics"])
        self.assertTrue(
            all(
                edge["source"] in _node_ids(top_two)
                and edge["target"] in _node_ids(top_two)
                for edge in top_two["edges"]
            )
        )
        self.assertTrue(
            any("Se muestran los 2" in warning for warning in top_two["warnings"])
        )

    def test_bridge_entity_has_highest_betweenness(self) -> None:
        bridge = _sentences(
            (DOC_A, "s1", ("minero", "coop")),
            (DOC_A, "s2", ("coop", "podas")),
            (DOC_A, "s3", ("podas", "rio")),
            (DOC_A, "s4", ("podas", "plan")),
        )
        network = build_explorer_network(
            bridge,
            ExplorerFilters(
                minimum_node_document_count=1,
                ranking_metric="betweenness",
                top_n=None,
            ),
        )

        self.assertEqual(network["nodes"][0]["id"], "podas")
        self.assertEqual(network["metric_provenance"]["betweenness"], "exact")

    def test_empty_results_return_warnings_instead_of_errors(self) -> None:
        no_mentions = build_explorer_network([], ExplorerFilters())
        too_strict = build_explorer_network(
            CORPUS, ExplorerFilters(minimum_node_document_count=10)
        )

        self.assertEqual(no_mentions["nodes"], [])
        self.assertTrue(no_mentions["warnings"])
        self.assertEqual(too_strict["edges"], [])
        self.assertIn("minimum_node_document_count", too_strict["warnings"][0])


class CompareRankingsTests(unittest.TestCase):
    def test_reports_central_node_change_and_top_k_movement(self) -> None:
        early = build_explorer_network(
            _sentences(
                (DOC_A, "s1", ("coop", "podas")),
                (DOC_A, "s2", ("coop", "plan")),
                (DOC_A, "s3", ("coop", "rio")),
            ),
            ExplorerFilters(
                minimum_node_document_count=1, ranking_metric="degree", top_n=None
            ),
        )
        late = build_explorer_network(
            _sentences(
                (DOC_B, "s1", ("vivero", "podas")),
                (DOC_B, "s2", ("vivero", "plan")),
                (DOC_B, "s3", ("vivero", "rio")),
                (DOC_B, "s4", ("vivero", "minero")),
            ),
            ExplorerFilters(
                minimum_node_document_count=1, ranking_metric="degree", top_n=None
            ),
        )

        comparison = compare_rankings(
            {"2021-2023": early, "2024-2026": late}, metric="degree", top_k=1
        )

        self.assertEqual(
            comparison["central_by_period"]["2021-2023"]["degree"]["id"], "coop"
        )
        self.assertEqual(
            comparison["central_by_period"]["2024-2026"]["degree"]["id"], "vivero"
        )
        change = comparison["changes"][0]
        self.assertEqual([item["id"] for item in change["entered"]], ["vivero"])
        self.assertEqual([item["id"] for item in change["left"]], ["coop"])
        coop = next(item for item in comparison["trajectories"] if item["id"] == "coop")
        self.assertEqual(coop["points"][0]["rank"], 1)
        self.assertIsNone(coop["points"][1]["rank"])


class ExplorerServiceTests(unittest.TestCase):
    @staticmethod
    def _document(document_id: str, year: int | None) -> SimpleNamespace:
        return SimpleNamespace(
            id=UUID(document_id),
            original_filename=f"{document_id[-1]}.pdf",
            year=year,
            incubator_number=1,
            language="es",
            document_type="technical_report",
        )

    def test_scope_defaults_to_agroforestry_and_all_disables_the_filter(self) -> None:
        self.assertEqual(ExplorerScope().productive_sector, "Agroforestry")
        self.assertEqual(
            _scope(ExplorerNetworkRequest()).productive_sector, "Agroforestry"
        )
        self.assertIsNone(
            _scope(ExplorerNetworkRequest(productive_sector="all")).productive_sector
        )
        with self.assertRaises(ValidationError):
            ExplorerNetworkRequest(productive_sector="Mining")

    def test_scoped_documents_query_filters_by_sector_only_when_requested(self) -> None:
        def compiled_where(scope: ExplorerScope) -> str:
            db = Mock()
            db.execute.return_value.all.return_value = []
            _scoped_documents(db, scope)
            statement = db.execute.call_args.args[0]
            return str(statement.whereclause)

        self.assertIn("productive_sector", compiled_where(ExplorerScope()))
        self.assertNotIn(
            "productive_sector", compiled_where(ExplorerScope(productive_sector=None))
        )

    def test_unknown_period_is_rejected(self) -> None:
        with self.assertRaises(ExplorerFiltroInvalido):
            ExplorerService.network(
                Mock(), ExplorerScope(period="1999-2000"), ExplorerFilters()
            )

    def test_network_loads_mentions_only_for_scoped_documents(self) -> None:
        documents = [self._document(DOC_A, 2022), self._document(DOC_B, 2023)]
        with (
            patch("src.services.explorer._scoped_documents", return_value=documents),
            patch(
                "src.services.explorer.load_db_mentions", return_value=CORPUS
            ) as load,
        ):
            payload = ExplorerService.network(
                Mock(), ExplorerScope(period="2021-2023"), ExplorerFilters()
            )

        self.assertEqual(load.call_args.kwargs["document_ids"], [DOC_A, DOC_B])
        self.assertEqual(payload["scope"]["period"], "2021-2023")
        self.assertEqual(payload["scope"]["document_count"], 2)
        self.assertEqual(payload["version"], "entity-explorer-v1")
        ExplorerNetworkResponse.model_validate(payload)

    def test_network_without_documents_skips_database_mentions(self) -> None:
        with (
            patch("src.services.explorer._scoped_documents", return_value=[]),
            patch("src.services.explorer.load_db_mentions") as load,
        ):
            payload = ExplorerService.network(
                Mock(), ExplorerScope(), ExplorerFilters()
            )

        load.assert_not_called()
        self.assertEqual(payload["nodes"], [])
        self.assertIn("No hay documentos listos", payload["warnings"][0])

    def test_compare_computes_each_period_without_top_n(self) -> None:
        calls = []

        def fake_network(db, scope, filters):
            calls.append((scope.period, filters.top_n))
            return [], build_explorer_network(
                CORPUS, ExplorerFilters(minimum_node_document_count=1, top_n=None)
            )

        with patch.object(
            ExplorerService, "_network_for_scope", side_effect=fake_network
        ):
            payload = ExplorerService.compare(
                Mock(),
                ExplorerScope(),
                ExplorerFilters(top_n=10),
                periods=["2024-2026", "2021-2023"],
                top_k=3,
            )

        self.assertEqual(calls, [("2021-2023", None), ("2024-2026", None)])
        # La respuesta debe cumplir el contrato público completo.
        ExplorerCompareResponse.model_validate(payload)
        self.assertEqual(payload["periods"], ["2021-2023", "2024-2026"])
        self.assertEqual(len(payload["period_summaries"]), 2)


class ExplorerApiTests(unittest.TestCase):
    def test_openapi_exposes_explorer_endpoints(self) -> None:
        paths = app.openapi()["paths"]

        self.assertIn("get", paths["/analysis/explorer/v1/meta"])
        self.assertIn("post", paths["/analysis/explorer/v1/network"])
        self.assertIn("post", paths["/analysis/explorer/v1/compare"])
        self.assertIn("get", paths["/analysis/explorer/v1/evidence"])

    def test_request_schema_rejects_unknown_categories_and_bad_pairs(self) -> None:
        with self.assertRaises(ValidationError):
            ExplorerNetworkRequest(categories=["GOVERNANZA"])
        with self.assertRaises(ValidationError):
            ExplorerNetworkRequest(link_mode="pairs", category_pairs=[["CHAR"]])
        with self.assertRaises(ValidationError):
            ExplorerCompareRequest(periods=["2021-2023"])

    def test_network_endpoint_maps_filter_errors_to_422(self) -> None:
        body = ExplorerNetworkRequest(categories=["CHAR"], link_mode="between")
        with (
            patch("src.services.explorer._scoped_documents", return_value=[]),
            self.assertRaises(ExplorerFiltroInvalido) as raised,
        ):
            explorer_network(body=body, db=Mock())

        self.assertEqual(raised.exception.codigo_http, 422)
        self.assertIn("between", raised.exception.mensaje)

    def test_load_db_mentions_with_empty_document_list_returns_nothing(self) -> None:
        db = Mock()

        self.assertEqual(load_db_mentions(document_ids=[], db=db), [])
        db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
