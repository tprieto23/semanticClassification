"""add cleaning metrics columns to documents

Revision ID: 1e6e4c60daa8
Revises: 001_initial
Create Date: 2026-05-04 22:21:57.977673

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1e6e4c60daa8'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('original_char_count', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('cleaned_char_count', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('reduction_percentage', sa.Float(), nullable=True))
    op.add_column('documents', sa.Column('cleaning_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'cleaning_metadata')
    op.drop_column('documents', 'reduction_percentage')
    op.drop_column('documents', 'cleaned_char_count')
    op.drop_column('documents', 'original_char_count')
