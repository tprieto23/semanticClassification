"""drop unused tables entities relationships graphs metrics

Revision ID: 1b139bb7a734
Revises: 05698e6c8933
Create Date: 2026-06-04 01:58:36.272354

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1b139bb7a734'
down_revision = '05698e6c8933'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS relationships CASCADE")
    op.execute("DROP TABLE IF EXISTS metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS entities CASCADE")
    op.execute("DROP TABLE IF EXISTS graphs CASCADE")


def downgrade() -> None:
    pass
