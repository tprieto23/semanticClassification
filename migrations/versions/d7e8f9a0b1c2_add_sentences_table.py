"""add sentences table

Revision ID: d7e8f9a0b1c2
Revises: d5e6f7a8b9c0
Create Date: 2026-09-03

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d7e8f9a0b1c2"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sentences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("sentence_id", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "sentence_id",
            name="uq_sentences_document_sentence",
        ),
    )
    op.create_index(
        "ix_sentences_document_id",
        "sentences",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sentences_document_id", table_name="sentences")
    op.drop_table("sentences")
