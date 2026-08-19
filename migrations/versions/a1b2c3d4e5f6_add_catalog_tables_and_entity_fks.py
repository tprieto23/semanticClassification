"""add_catalog_tables_and_entity_fks

Revision ID: a1b2c3d4e5f6
Revises: d4e5f6a7b8c9
Create Date: 2026-07-13

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'catalog_labels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'catalog_attributes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'catalog_ambiguity_levels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'catalog_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('label_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['label_id'], ['catalog_labels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'catalog_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('attribute_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['attribute_id'], ['catalog_attributes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'catalog_nodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('type_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['type_id'], ['catalog_types.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Seed labels
    labels_table = sa.table('catalog_labels', sa.column('id', sa.Integer), sa.column('name', sa.Text))
    op.bulk_insert(labels_table, [
        {'id': 1, 'name': 'CHAR'},
        {'id': 2, 'name': 'LOC'},
        {'id': 3, 'name': 'INFRA'},
        {'id': 4, 'name': 'GOV'},
        {'id': 5, 'name': 'PRAC'},
    ])

    # Seed ambiguity levels
    amb_table = sa.table('catalog_ambiguity_levels', sa.column('id', sa.Integer), sa.column('name', sa.Text))
    op.bulk_insert(amb_table, [
        {'id': 1, 'name': 'low'},
        {'id': 2, 'name': 'medium'},
        {'id': 3, 'name': 'high'},
    ])

    # Alter entities table
    op.add_column('entities', sa.Column('label_id', sa.Integer(), nullable=True))
    op.add_column('entities', sa.Column('type_id', sa.Integer(), nullable=True))
    op.add_column('entities', sa.Column('node_id', sa.Integer(), nullable=True))
    op.add_column('entities', sa.Column('attribute_id', sa.Integer(), nullable=True))
    op.add_column('entities', sa.Column('value_id', sa.Integer(), nullable=True))
    op.add_column('entities', sa.Column('ambiguity_id', sa.Integer(), nullable=True))

    op.create_foreign_key(None, 'entities', 'catalog_labels', ['label_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'entities', 'catalog_types', ['type_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'entities', 'catalog_nodes', ['node_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'entities', 'catalog_attributes', ['attribute_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'entities', 'catalog_values', ['value_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'entities', 'catalog_ambiguity_levels', ['ambiguity_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint(None, 'entities', type_='foreignkey')
    op.drop_constraint(None, 'entities', type_='foreignkey')
    op.drop_constraint(None, 'entities', type_='foreignkey')
    op.drop_constraint(None, 'entities', type_='foreignkey')
    op.drop_constraint(None, 'entities', type_='foreignkey')
    op.drop_constraint(None, 'entities', type_='foreignkey')

    op.drop_column('entities', 'ambiguity_id')
    op.drop_column('entities', 'value_id')
    op.drop_column('entities', 'attribute_id')
    op.drop_column('entities', 'node_id')
    op.drop_column('entities', 'type_id')
    op.drop_column('entities', 'label_id')

    op.drop_table('catalog_nodes')
    op.drop_table('catalog_values')
    op.drop_table('catalog_types')
    op.drop_table('catalog_ambiguity_levels')
    op.drop_table('catalog_attributes')
    op.drop_table('catalog_labels')
