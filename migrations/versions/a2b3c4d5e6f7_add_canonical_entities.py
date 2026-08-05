"""add_canonical_entities

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-05

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_entities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "entities",
        sa.Column("canonical_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_entities_canonical_id",
        "entities",
        "canonical_entities",
        ["canonical_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_entities_canonical_id", "entities", ["canonical_id"])


def downgrade() -> None:
    op.drop_index("ix_entities_canonical_id", table_name="entities")
    op.drop_constraint("fk_entities_canonical_id", "entities", type_="foreignkey")
    op.drop_column("entities", "canonical_id")
    op.drop_table("canonical_entities")
