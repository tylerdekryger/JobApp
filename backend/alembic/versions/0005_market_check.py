"""add jobs.market_check_* columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("market_check_summary", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("market_check_url", sa.String(length=1024), nullable=True))
    op.add_column("jobs", sa.Column("market_check_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "market_check_at")
    op.drop_column("jobs", "market_check_url")
    op.drop_column("jobs", "market_check_summary")
