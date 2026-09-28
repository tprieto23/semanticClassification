"""Add ingestion classification fields to documents.

Revision ID: a4b5c6d7e8f9
Revises: f3c4d5e6f7a8
Create Date: 2026-09-28
"""

import sqlalchemy as sa
from alembic import op

revision = "a4b5c6d7e8f9"
down_revision = "f3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("year", sa.SmallInteger(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("productive_sector", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("document_type", sa.String(length=50), nullable=True),
    )
    op.create_check_constraint(
        "ck_documents_year",
        "documents",
        "year BETWEEN 1000 AND 9999",
    )
    op.create_check_constraint(
        "ck_documents_productive_sector",
        "documents",
        "productive_sector IN ('Agroforestry')",
    )
    op.create_check_constraint(
        "ck_documents_document_type",
        "documents",
        "document_type IN ('academic', 'technical_report', 'project_report', "
        "'policy_document', 'manual_or_guide', 'institutional_document', 'other')",
    )
    op.create_index("ix_documents_year", "documents", ["year"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])


def downgrade() -> None:
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_year", table_name="documents")
    op.drop_constraint(
        "ck_documents_document_type", "documents", type_="check"
    )
    op.drop_constraint(
        "ck_documents_productive_sector", "documents", type_="check"
    )
    op.drop_constraint("ck_documents_year", "documents", type_="check")
    op.drop_column("documents", "document_type")
    op.drop_column("documents", "productive_sector")
    op.drop_column("documents", "year")
