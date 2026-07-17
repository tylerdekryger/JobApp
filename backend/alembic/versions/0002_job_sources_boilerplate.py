"""add description_boilerplate_prefix to job_sources

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_sources",
        sa.Column("description_boilerplate_prefix", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_sources", "description_boilerplate_prefix")
