"""Persist deterministic meta-network relationships.

Revision ID: f3c4d5e6f7a8
Revises: f2b3c4d5e6f7
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3c4d5e6f7a8"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_network_source_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("clustering_sha256", sa.Text(), nullable=False),
        sa.Column("source_graph_sha256", sa.Text(), nullable=False),
        sa.Column("source_canonical_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_canonical_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_category", sa.Text(), nullable=True),
        sa.Column("target_category", sa.Text(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("sentence_count", sa.Integer(), nullable=True),
        sa.Column("document_count", sa.Integer(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_canonical_id"], ["canonical_entities.id"],
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_canonical_id"], ["canonical_entities.id"],
                                ondelete="RESTRICT"),
        sa.UniqueConstraint("clustering_sha256", "source_canonical_id",
                            "target_canonical_id", name="uq_meta_source_edge_partition_pair"),
    )
    op.create_index("ix_meta_source_edges_partition", "semantic_network_source_edges",
                    ["clustering_sha256"])
    op.create_index("ix_meta_source_edges_source", "semantic_network_source_edges",
                    ["source_canonical_id"])
    op.create_index("ix_meta_source_edges_target", "semantic_network_source_edges",
                    ["target_canonical_id"])

    op.create_table(
        "semantic_node_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("clustering_sha256", sa.Text(), nullable=False),
        sa.Column("source_graph_sha256", sa.Text(), nullable=False),
        sa.Column("source_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("formula_version", sa.Text(), nullable=False),
        sa.Column("minimum_source_edge_weight", sa.Float(), nullable=False),
        sa.Column("source_edge_count", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("mean_source_weight", sa.Float(), nullable=False),
        sa.Column("sentence_support_sum", sa.Integer(), nullable=False),
        sa.Column("document_support_sum", sa.Integer(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_node_id"], ["semantic_nodes.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["semantic_nodes.id"],
                                ondelete="CASCADE"),
        sa.UniqueConstraint("clustering_sha256", "source_node_id", "target_node_id",
                            "formula_version", "minimum_source_edge_weight",
                            name="uq_meta_relationship_formula"),
    )
    op.create_index("ix_meta_relationships_partition", "semantic_node_relationships",
                    ["clustering_sha256"])
    op.create_index("ix_meta_relationships_source", "semantic_node_relationships",
                    ["source_node_id"])
    op.create_index("ix_meta_relationships_target", "semantic_node_relationships",
                    ["target_node_id"])


def downgrade() -> None:
    op.drop_index("ix_meta_relationships_target", table_name="semantic_node_relationships")
    op.drop_index("ix_meta_relationships_source", table_name="semantic_node_relationships")
    op.drop_index("ix_meta_relationships_partition", table_name="semantic_node_relationships")
    op.drop_table("semantic_node_relationships")
    op.drop_index("ix_meta_source_edges_target", table_name="semantic_network_source_edges")
    op.drop_index("ix_meta_source_edges_source", table_name="semantic_network_source_edges")
    op.drop_index("ix_meta_source_edges_partition", table_name="semantic_network_source_edges")
    op.drop_table("semantic_network_source_edges")
