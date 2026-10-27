"""Allow corpus-specific free-text document types.

Revision ID: d8e9f0a1b2c3
Revises: c6d7e8f9a0b1
"""

from alembic import op


revision = "d8e9f0a1b2c3"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_documents_document_type", "documents", type_="check")


def downgrade() -> None:
    op.create_check_constraint(
        "ck_documents_document_type",
        "documents",
        "document_type IN ('academic', 'technical_report', 'project_report', "
        "'policy_document', 'manual_or_guide', 'institutional_document', 'other')",
    )
