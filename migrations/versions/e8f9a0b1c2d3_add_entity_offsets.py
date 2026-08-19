"""add_entity_offsets

Revision ID: e8f9a0b1c2d3
Revises: c7d8e9f0a1b2
Create Date: 2026-08-03

"""

import sqlalchemy as sa
from alembic import op


revision = "e8f9a0b1c2d3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entities", sa.Column("position_start", sa.Integer(), nullable=True))
    op.add_column("entities", sa.Column("position_end", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("entities", "position_end")
    op.drop_column("entities", "position_start")
