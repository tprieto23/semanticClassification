"""Normalize legacy GOV category pairs stored in source-edge metadata.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-09-28
"""

from alembic import op

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE semantic_network_source_edges
        SET attributes = jsonb_set(
            attributes,
            '{category_pair}',
            to_jsonb(replace(attributes->>'category_pair', 'GOV', 'RUL')),
            false
        )
        WHERE attributes->>'category_pair' LIKE '%GOV%'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE semantic_network_source_edges
        SET attributes = jsonb_set(
            attributes,
            '{category_pair}',
            to_jsonb(replace(attributes->>'category_pair', 'RUL', 'GOV')),
            false
        )
        WHERE attributes->>'category_pair' LIKE '%RUL%'
        """
    )
