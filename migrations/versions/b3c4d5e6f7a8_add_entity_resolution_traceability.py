"""add entity resolution traceability

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-12

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entities", sa.Column("resolution_method", sa.Text(), nullable=True))
    op.add_column("entities", sa.Column("resolution_score", sa.Float(), nullable=True))
    op.add_column("entities", sa.Column("resolution_version", sa.Text(), nullable=True))
    op.add_column(
        "entities",
        sa.Column("resolution_details", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "canonical_entity_aliases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias_text", sa.Text(), nullable=False),
        sa.Column("normalized_alias", sa.Text(), nullable=False),
        sa.Column("resolution_method", sa.Text(), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["canonical_id"], ["canonical_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["documents.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_id",
            "normalized_alias",
            name="uq_canonical_entity_aliases_canonical_normalized",
        ),
    )
    op.create_index(
        "ix_canonical_entity_aliases_canonical_id",
        "canonical_entity_aliases",
        ["canonical_id"],
    )
    op.create_index(
        "ix_canonical_entity_aliases_normalized_alias",
        "canonical_entity_aliases",
        ["normalized_alias"],
    )
    op.create_index(
        "ix_canonical_entity_aliases_source_document_id",
        "canonical_entity_aliases",
        ["source_document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_canonical_entity_aliases_source_document_id",
        table_name="canonical_entity_aliases",
    )
    op.drop_index(
        "ix_canonical_entity_aliases_normalized_alias",
        table_name="canonical_entity_aliases",
    )
    op.drop_index(
        "ix_canonical_entity_aliases_canonical_id",
        table_name="canonical_entity_aliases",
    )
    op.drop_table("canonical_entity_aliases")

    op.drop_column("entities", "resolution_details")
    op.drop_column("entities", "resolution_version")
    op.drop_column("entities", "resolution_score")
    op.drop_column("entities", "resolution_method")
