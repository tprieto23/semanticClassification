"""recreate entities table

Revision ID: b8e3f2a1c4d5
Revises: cfe959221fc7
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import pgvector.sqlalchemy


revision = 'b8e3f2a1c4d5'
down_revision = 'cfe959221fc7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'entities',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('normalized_text', sa.Text(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('position_start', sa.Integer(), nullable=True),
        sa.Column('position_end', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(384), nullable=True),
    )

    op.create_index('ix_entities_document', 'entities', ['document_id'])
    op.create_index('ix_entities_category', 'entities', ['category'])


def downgrade() -> None:
    op.drop_index('ix_entities_category', table_name='entities')
    op.drop_index('ix_entities_document', table_name='entities')
    op.drop_table('entities')
