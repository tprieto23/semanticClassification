"""Persist accepted Leiden communities as semantic nodes.

Revision ID: f2b3c4d5e6f7
Revises: d7e8f9a0b1c2
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f2b3c4d5e6f7"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("projection_id", sa.Text(), nullable=False),
        sa.Column("artifact_source", sa.Text(), nullable=False),
        sa.Column("community_id", sa.Text(), nullable=False),
        sa.Column("clustering_sha256", sa.Text(), nullable=False),
        sa.Column("source_graph_sha256", sa.Text(), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("incubator_support", postgresql.JSONB(), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("generation", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("clustering_sha256", "community_id",
                            name="uq_semantic_nodes_partition_community"),
    )
    op.create_index("ix_semantic_nodes_status", "semantic_nodes", ["status"])
    op.create_table(
        "semantic_node_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("semantic_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["semantic_node_id"], ["semantic_nodes.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["canonical_id"], ["canonical_entities.id"],
                                ondelete="RESTRICT"),
        sa.UniqueConstraint("semantic_node_id", "canonical_id",
                            name="uq_semantic_node_member"),
    )
    op.create_index("ix_semantic_node_members_semantic_node_id",
                    "semantic_node_members", ["semantic_node_id"])
    op.create_index("ix_semantic_node_members_canonical_id",
                    "semantic_node_members", ["canonical_id"])


def downgrade() -> None:
    op.drop_index("ix_semantic_node_members_canonical_id", table_name="semantic_node_members")
    op.drop_index("ix_semantic_node_members_semantic_node_id", table_name="semantic_node_members")
    op.drop_table("semantic_node_members")
    op.drop_index("ix_semantic_nodes_status", table_name="semantic_nodes")
    op.drop_table("semantic_nodes")
