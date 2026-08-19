"""add language to documents

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-18

"""

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("language", sa.String(length=10), nullable=True),
    )
    op.create_index(
        "ix_documents_language",
        "documents",
        ["language"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_language", table_name="documents")
    op.drop_column("documents", "language")
