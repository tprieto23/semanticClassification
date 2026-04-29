"""initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-04-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import pgvector.sqlalchemy

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    op.create_table(
        'documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('original_filename', sa.Text(), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_type', sa.Text(), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger()),
        sa.Column('status', sa.Text(), nullable=False, default='raw'),
        sa.Column('uploaded_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('metadata', JSONB()),
    )
    
    op.create_table(
        'entities',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('normalized_text', sa.Text()),
        sa.Column('context', sa.Text()),
        sa.Column('position_start', sa.Integer()),
        sa.Column('position_end', sa.Integer()),
        sa.Column('confidence', sa.Float()),
        sa.Column('metadata', JSONB()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(384)),
    )
    
    op.create_table(
        'graphs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('file_path', sa.Text()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    
    op.create_table(
        'relationships',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('entity_source_id', UUID(as_uuid=True), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('entity_target_id', UUID(as_uuid=True), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('relationship_type', sa.Text()),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id')),
        sa.Column('metadata', JSONB()),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    
    op.create_table(
        'metrics',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('graph_id', UUID(as_uuid=True), sa.ForeignKey('graphs.id')),
        sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('entities.id')),
        sa.Column('metric_name', sa.Text(), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('calculated_at', sa.DateTime(), default=sa.func.now()),
    )
    
    op.create_index('ix_entities_document', 'entities', ['document_id'])
    op.create_index('ix_entities_category', 'entities', ['category'])
    op.create_index('ix_relationships_source', 'relationships', ['entity_source_id'])
    op.create_index('ix_relationships_target', 'relationships', ['entity_target_id'])
    op.create_index('ix_relationships_document', 'relationships', ['document_id'])
    op.create_index('ix_metrics_graph', 'metrics', ['graph_id'])
    op.create_index('ix_metrics_entity', 'metrics', ['entity_id'])
    
    op.create_index(
        'ix_entities_embedding',
        'entities',
        ['embedding'],
        postgresql_using='ivfflat',
        postgresql_with={'lists': 100},
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )


def downgrade() -> None:
    op.drop_index('ix_entities_embedding', table_name='entities')
    op.drop_index('ix_metrics_entity', table_name='metrics')
    op.drop_index('ix_metrics_graph', table_name='metrics')
    op.drop_index('ix_relationships_document', table_name='relationships')
    op.drop_index('ix_relationships_target', table_name='relationships')
    op.drop_index('ix_relationships_source', table_name='relationships')
    op.drop_index('ix_entities_category', table_name='entities')
    op.drop_index('ix_entities_document', table_name='entities')
    
    op.drop_table('metrics')
    op.drop_table('relationships')
    op.drop_table('graphs')
    op.drop_table('entities')
    op.drop_table('documents')
    op.execute('DROP EXTENSION IF EXISTS vector')
