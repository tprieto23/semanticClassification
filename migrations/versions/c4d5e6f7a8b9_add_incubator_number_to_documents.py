"""add incubator number to documents

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-08-13

"""

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("incubator_number", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_documents_incubator_number",
        "documents",
        "incubator_number BETWEEN 1 AND 8",
    )
    op.create_index(
        "ix_documents_incubator_number",
        "documents",
        ["incubator_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_incubator_number", table_name="documents")
    op.drop_constraint(
        "ck_documents_incubator_number",
        "documents",
        type_="check",
    )
    op.drop_column("documents", "incubator_number")
