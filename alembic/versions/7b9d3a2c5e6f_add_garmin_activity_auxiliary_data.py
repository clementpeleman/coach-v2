"""add garmin activity auxiliary data

Revision ID: 7b9d3a2c5e6f
Revises: 2f4d9c0f5e12
Create Date: 2026-05-17 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b9d3a2c5e6f"
down_revision: Union[str, Sequence[str], None] = "2f4d9c0f5e12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "garmin_activity_data",
        sa.Column("summary_type", sa.String(), nullable=False, server_default="activities"),
    )
    op.alter_column("garmin_activity_data", "summary_type", server_default=None)

    op.create_table(
        "garmin_activity_auxiliary_data",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("summary_id", sa.String(), nullable=False),
        sa.Column("summary_type", sa.String(), nullable=False),
        sa.Column("activity_id", sa.String(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("start_time_offset", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user_profile.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("summary_type", "summary_id", name="uq_garmin_activity_aux_type_summary"),
    )


def downgrade() -> None:
    op.drop_table("garmin_activity_auxiliary_data")
    op.drop_column("garmin_activity_data", "summary_type")
