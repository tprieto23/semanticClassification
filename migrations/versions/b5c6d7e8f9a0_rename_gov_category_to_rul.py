"""Rename the GOV semantic category to RUL.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-28
"""

from alembic import op

revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE entities SET category = 'RUL' WHERE category = 'GOV'")
    op.execute(
        "UPDATE canonical_entities SET category = 'RUL' WHERE category = 'GOV'"
    )
    op.execute(
        "UPDATE semantic_node_members SET category = 'RUL' WHERE category = 'GOV'"
    )
    op.execute(
        "UPDATE semantic_network_source_edges SET source_category = 'RUL' "
        "WHERE source_category = 'GOV'"
    )
    op.execute(
        "UPDATE semantic_network_source_edges SET target_category = 'RUL' "
        "WHERE target_category = 'GOV'"
    )
    op.execute(
        "UPDATE semantic_nodes SET projection_id = 'prac-infra-rul-v2' "
        "WHERE projection_id = 'prac-infra-gov-v1'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE semantic_nodes SET projection_id = 'prac-infra-gov-v1' "
        "WHERE projection_id = 'prac-infra-rul-v2'"
    )
    op.execute(
        "UPDATE semantic_network_source_edges SET target_category = 'GOV' "
        "WHERE target_category = 'RUL'"
    )
    op.execute(
        "UPDATE semantic_network_source_edges SET source_category = 'GOV' "
        "WHERE source_category = 'RUL'"
    )
    op.execute(
        "UPDATE semantic_node_members SET category = 'GOV' WHERE category = 'RUL'"
    )
    op.execute(
        "UPDATE canonical_entities SET category = 'GOV' WHERE category = 'RUL'"
    )
    op.execute("UPDATE entities SET category = 'GOV' WHERE category = 'RUL'")
