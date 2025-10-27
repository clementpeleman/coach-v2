"""add_garmin_tables

Revision ID: c32de388fe01
Revises: a6c410a1b271
Create Date: 2025-10-08 11:07:42.368431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c32de388fe01'
down_revision: Union[str, Sequence[str], None] = 'a6c410a1b271'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add garmin_user_id to user_profile
    op.add_column('user_profile', sa.Column('garmin_user_id', sa.String(), nullable=True))
    op.create_unique_constraint('uq_user_profile_garmin_user_id', 'user_profile', ['garmin_user_id'])

    # Make garmin_email and garmin_password nullable
    op.alter_column('user_profile', 'garmin_email', nullable=True)
    op.alter_column('user_profile', 'garmin_password', nullable=True)

    # Create garmin_tokens table
    op.create_table(
        'garmin_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('garmin_user_id', sa.String(), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('token_type', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('refresh_expires_at', sa.DateTime(), nullable=False),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_profile.user_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('garmin_user_id')
    )

    # Create garmin_health_data table
    op.create_table(
        'garmin_health_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('summary_id', sa.String(), nullable=False),
        sa.Column('summary_type', sa.String(), nullable=False),
        sa.Column('calendar_date', sa.String(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('start_time_offset', sa.Integer(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('data', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_profile.user_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('summary_id')
    )

    # Create garmin_activity_data table
    op.create_table(
        'garmin_activity_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('summary_id', sa.String(), nullable=False),
        sa.Column('activity_id', sa.String(), nullable=True),
        sa.Column('activity_type', sa.String(), nullable=False),
        sa.Column('activity_name', sa.String(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('start_time_offset', sa.Integer(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('distance', sa.Float(), nullable=True),
        sa.Column('calories', sa.Integer(), nullable=True),
        sa.Column('average_heart_rate', sa.Integer(), nullable=True),
        sa.Column('max_heart_rate', sa.Integer(), nullable=True),
        sa.Column('device_name', sa.String(), nullable=True),
        sa.Column('manual', sa.Boolean(), nullable=True),
        sa.Column('data', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_profile.user_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('summary_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('garmin_activity_data')
    op.drop_table('garmin_health_data')
    op.drop_table('garmin_tokens')

    op.drop_constraint('uq_user_profile_garmin_user_id', 'user_profile', type_='unique')
    op.drop_column('user_profile', 'garmin_user_id')

    op.alter_column('user_profile', 'garmin_email', nullable=False)
    op.alter_column('user_profile', 'garmin_password', nullable=False)
