import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import networkx as nx
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from src.analysis.graph_paths import semantic_network_filename
from src.api.schemas.semantic_relationships import (
    MetaNetworkGraphMLExportRequest,
    MetaRelationshipBuildRequest,
)
from src.config import settings
from src.models.canonical_entities import CanonicalEntity
from src.models.database import Base
from src.models.semantic_nodes import SemanticNode, SemanticNodeMember
from src.models.semantic_relationships import (
    SemanticNetworkSourceEdge,
    SemanticNodeRelationship,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(type_, compiler, **kw):
    return "JSON"


# The relationship builder is deterministic, but the shared DocumentoError
# currently lives in the document service, whose optional Anthropic dependency
# is not needed by these unit tests.
if "anthropic" not in sys.modules:
    sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=object)
if "src.services.documents" not in sys.modules:
    documents_stub = types.ModuleType("src.services.documents")
    class DocumentoError(Exception):
        def __init__(self, mensaje, codigo_http=409):
            self.mensaje = mensaje
            self.codigo_http = codigo_http
            super().__init__(mensaje)
    class DocumentoNoEncontrado(DocumentoError):
        pass
    documents_stub.DocumentoError = DocumentoError
    documents_stub.DocumentoNoEncontrado = DocumentoNoEncontrado
    sys.modules["src.services.documents"] = documents_stub

from src.services.semantic_relationships import (
    FORMULA_VERSION,
    SemanticRelationshipService,
    _ordered_pair,
)


class SemanticRelationshipTests(unittest.TestCase):
    def test_pairs_are_canonical_for_undirected_meta_edges(self):
        left, right = uuid4(), uuid4()
        self.assertEqual(_ordered_pair(left, right), _ordered_pair(right, left))
        self.assertEqual(set(_ordered_pair(left, right)), {left, right})

    def test_build_request_defaults_to_deterministic_zero_threshold(self):
        request = MetaRelationshipBuildRequest(
            artifact_source="official",
            clustering_sha256="a" * 64,
        )
        self.assertEqual(request.minimum_source_edge_weight, 0.0)
        self.assertTrue(request.require_accepted_nodes)
        self.assertEqual(FORMULA_VERSION, "meta-network-relationship-v1")

    def test_hash_and_threshold_are_validated(self):
        with self.assertRaises(ValueError):
            MetaRelationshipBuildRequest(
                artifact_source="official",
                clustering_sha256="invalid",
            )
        with self.assertRaises(ValueError):
            MetaRelationshipBuildRequest(
                artifact_source="official",
                clustering_sha256="b" * 64,
                minimum_source_edge_weight=-1,
            )

    def test_graphml_export_defaults_include_isolates(self):
        request = MetaNetworkGraphMLExportRequest(clustering_sha256="c" * 64)
        self.assertEqual(request.minimum_source_edge_weight, 0.0)
        self.assertTrue(request.include_isolates)
        self.assertEqual(
            semantic_network_filename("prac-infra-gov-v1"),
            "semantic_network_prac-infra-gov-v1",
        )


class SemanticRelationshipServiceTests(unittest.TestCase):
    clustering_sha256 = "a" * 64
    source_graph_sha256 = "b" * 64

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.graph_storage = Path(temporary.name) / "graphs"
        storage_patch = patch.object(settings, "STORAGE_GRAPHS", self.graph_storage)
        storage_patch.start()
        self.addCleanup(storage_patch.stop)

        self.engine = create_engine("sqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(
            self.engine,
            tables=[
                CanonicalEntity.__table__,
                SemanticNode.__table__,
                SemanticNodeMember.__table__,
                SemanticNetworkSourceEdge.__table__,
                SemanticNodeRelationship.__table__,
            ],
        )
        session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )
        self.db = session_factory()
        self.addCleanup(self.db.close)

        self.graph = self._seed_partition()
        self.metadata = {
            "projection_id": "prac-infra-gov-v1",
            "source": {"graphml_sha256": self.source_graph_sha256},
        }

    def _seed_partition(self):
        graph = nx.Graph()
        graph.graph["source_graph_sha256"] = self.source_graph_sha256
        communities = {
            "a1": ("C001", "PRAC", "Práctica A"),
            "a2": ("C001", "INFRA", "Infraestructura A"),
            "b1": ("C002", "GOV", "Gobernanza B"),
            "b2": ("C002", "PRAC", "Práctica B"),
            "isolated": ("C003", "INFRA", "Infraestructura aislada"),
            "unregistered": ("C004", "GOV", "Comunidad no registrada"),
        }
        canonical_ids = {key: uuid4() for key in communities}
        canonical_entities = []
        for key, (community_id, category, canonical_name) in communities.items():
            canonical_id = canonical_ids[key]
            graph.add_node(
                str(canonical_id),
                community_id=community_id,
                category=category,
                canonical_name=canonical_name,
                label=canonical_name,
            )
            canonical_entities.append(CanonicalEntity(
                id=canonical_id, canonical_name=canonical_name, category=category
            ))

        nodes_by_community = {}
        for community_id, keys, title in (
            ("C001", ("a1", "a2"), "Meta-node A"),
            ("C002", ("b1", "b2"), "Meta-node B"),
            ("C003", ("isolated",), "Meta-node aislado"),
        ):
            node = SemanticNode(
                id=uuid4(),
                projection_id="prac-infra-gov-v1",
                artifact_source="official",
                community_id=community_id,
                clustering_sha256=self.clustering_sha256,
                source_graph_sha256=self.source_graph_sha256,
                scope_type="corpus",
                scope_id=None,
                language="es",
                provenance={},
                incubator_support=[],
                document_count=1,
                status="accepted",
                title=title,
                description=f"Descripción de {title}",
                members=[
                    SemanticNodeMember(
                        canonical_id=canonical_ids[key],
                        canonical_name=communities[key][2],
                        category=communities[key][1],
                    )
                    for key in keys
                ],
            )
            nodes_by_community[community_id] = node

        def add_edge(left, right, weight, sentence_count, document_count):
            graph.add_edge(
                str(canonical_ids[left]),
                str(canonical_ids[right]),
                weight=weight,
                sentence_count=sentence_count,
                document_count=document_count,
            )

        # Intra-community edges must not create meta-edges.
        add_edge("a1", "a2", 40.0, 8, 5)
        add_edge("b1", "b2", 30.0, 7, 4)
        # These three cross-community edges aggregate into one relation.
        add_edge("a1", "b1", 2.5, 3, 2)
        add_edge("a2", "b2", 1.25, 2, 1)
        add_edge("a1", "b2", 0.5, 1, 1)
        # Edges to an unregistered community must not enter the meta-network.
        add_edge("a1", "unregistered", 10.0, 4, 3)
        add_edge("b2", "unregistered", 8.0, 5, 4)

        self.db.add_all(canonical_entities + list(nodes_by_community.values()))
        self.db.commit()
        return graph

    def _build(self):
        with (
            patch(
                "src.services.semantic_relationships._artifacts",
                return_value=(Path("leiden.graphml"), Path("leiden.json")),
            ),
            patch(
                "src.services.semantic_relationships._read_partition",
                return_value=(self.graph, self.metadata),
            ),
        ):
            return SemanticRelationshipService.build(
                self.db,
                projection_id="prac-infra-gov-v1",
                artifact_source="official",
                clustering_sha256=self.clustering_sha256,
                incubator_number=None,
                language="es",
                minimum_source_edge_weight=0.0,
                require_accepted_nodes=True,
                force_recompute=False,
            )

    def test_build_aggregates_only_cross_edges_between_registered_meta_nodes(self):
        result = self._build()

        self.assertEqual(result["counts"], {
            "semantic_nodes": 2,
            "relationships": 1,
            "source_edges": 3,
        })
        relationship = result["relationships"][0]
        self.assertEqual(
            {relationship["source_community_id"], relationship["target_community_id"]},
            {"C001", "C002"},
        )
        self.assertEqual(relationship["source_edge_count"], 3)
        self.assertAlmostEqual(relationship["weight"], 4.25)
        self.assertAlmostEqual(relationship["mean_source_weight"], 4.25 / 3)
        self.assertEqual(relationship["sentence_support_sum"], 6)
        self.assertEqual(relationship["document_support_sum"], 4)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(SemanticNetworkSourceEdge)),
            7,
        )

    def test_repeated_build_returns_cached_result_without_duplicating_rows(self):
        first = self._build()
        second = self._build()

        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(
            first["relationships"][0]["id"], second["relationships"][0]["id"]
        )
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(SemanticNetworkSourceEdge)),
            7,
        )
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(SemanticNodeRelationship)),
            1,
        )

    def test_graphml_export_preserves_relationship_metrics_and_isolates(self):
        self._build()

        exported = SemanticRelationshipService.export_graphml(
            self.db,
            clustering_sha256=self.clustering_sha256,
            minimum_source_edge_weight=0.0,
            include_isolates=True,
        )
        self.assertEqual(exported["counts"], {
            "nodes": 3,
            "relationships": 1,
            "isolates": 1,
        })
        graphml_path = self.graph_storage / exported["graphml_path"]
        graph = nx.read_graphml(graphml_path)
        self.assertEqual(
            {attrs["community_id"] for _, attrs in graph.nodes(data=True)},
            {"C001", "C002", "C003"},
        )
        edge = next(iter(graph.edges(data=True)))[2]
        self.assertAlmostEqual(float(edge["weight"]), 4.25)
        self.assertEqual(int(edge["source_edge_count"]), 3)
        self.assertEqual(int(edge["sentence_support_sum"]), 6)
        self.assertEqual(int(edge["document_support_sum"]), 4)

        without_isolates = SemanticRelationshipService.export_graphml(
            self.db,
            clustering_sha256=self.clustering_sha256,
            minimum_source_edge_weight=0.0,
            include_isolates=False,
        )
        self.assertEqual(without_isolates["counts"], {
            "nodes": 2,
            "relationships": 1,
            "isolates": 0,
        })
