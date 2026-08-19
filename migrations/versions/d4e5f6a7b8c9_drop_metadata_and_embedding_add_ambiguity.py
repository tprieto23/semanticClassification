"""drop_metadata_and_embedding_add_ambiguity

Revision ID: d4e5f6a7b8c9
Revises: 3e0efedcaa04
Create Date: 2026-07-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import pgvector.sqlalchemy


revision = 'd4e5f6a7b8c9'
down_revision = '3e0efedcaa04'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('entities', 'metadata')
    op.drop_column('entities', 'embedding')
    op.add_column('entities', sa.Column('ambiguity', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('entities', 'ambiguity')
    op.add_column('entities', sa.Column('embedding', pgvector.sqlalchemy.Vector(384), nullable=True))
    op.add_column('entities', sa.Column('metadata', JSONB(), nullable=True))
