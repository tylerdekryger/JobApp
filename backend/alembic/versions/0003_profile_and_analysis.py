"""add user_profile table and job fit/gap analysis columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resume_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("resume_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("jobs", sa.Column("fit_summary", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("gap_summary", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("analysis_resume_hash", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "analyzed_at")
    op.drop_column("jobs", "analysis_resume_hash")
    op.drop_column("jobs", "gap_summary")
    op.drop_column("jobs", "fit_summary")
    op.drop_table("user_profile")
