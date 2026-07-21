"""remove_normalized_text_position_and_confidence_from_entities

Revision ID: 3e0efedcaa04
Revises: 5ea1bb7e236a
Create Date: 2026-07-10 04:23:56.954137

"""
from alembic import op
import sqlalchemy as sa


revision = '3e0efedcaa04'
down_revision = '5ea1bb7e236a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('entities', 'confidence')
    op.drop_column('entities', 'position_start')
    op.drop_column('entities', 'position_end')
    op.drop_column('entities', 'normalized_text')


def downgrade() -> None:
    op.add_column('entities', sa.Column('normalized_text', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('entities', sa.Column('position_end', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('entities', sa.Column('position_start', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('entities', sa.Column('confidence', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
