"""add_entity_sentence_id

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-08-04

"""

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entities", sa.Column("sentence_id", sa.Text(), nullable=True))
    op.create_index("ix_entities_sentence_id", "entities", ["sentence_id"])


def downgrade() -> None:
    op.drop_index("ix_entities_sentence_id", table_name="entities")
    op.drop_column("entities", "sentence_id")
