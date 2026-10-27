"""Restrict document years to the corpus range.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
"""

from alembic import op


revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_documents_year", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_year",
        "documents",
        "year BETWEEN 1990 AND 2030",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_year", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_year",
        "documents",
        "year BETWEEN 1000 AND 9999",
    )
