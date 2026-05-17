"""add garmin webhook events

Revision ID: 91b2c3d4e5f6
Revises: 7b9d3a2c5e6f
Create Date: 2026-05-17 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "91b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7b9d3a2c5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "garmin_webhook_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("garmin_user_id", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("summary_types", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=True),
        sa.Column("callback_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user_profile.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_garmin_webhook_events_user_created", "garmin_webhook_events", ["user_id", "created_at"])
    op.create_index("ix_garmin_webhook_events_source_status", "garmin_webhook_events", ["source", "status"])


def downgrade() -> None:
    op.drop_index("ix_garmin_webhook_events_source_status", table_name="garmin_webhook_events")
    op.drop_index("ix_garmin_webhook_events_user_created", table_name="garmin_webhook_events")
    op.drop_table("garmin_webhook_events")
