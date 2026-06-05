"""remove legacy cleaning columns from documents

Revision ID: 05698e6c8933
Revises: 1e6e4c60daa8
Create Date: 2026-06-04 01:53:58.133001

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '05698e6c8933'
down_revision = '1e6e4c60daa8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("documents", "original_char_count")
    op.drop_column("documents", "cleaned_char_count")
    op.drop_column("documents", "reduction_percentage")
    op.drop_column("documents", "cleaning_metadata")


def downgrade() -> None:
    op.add_column("documents", sa.Column("original_char_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("cleaned_char_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("reduction_percentage", sa.Float(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("cleaning_metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
