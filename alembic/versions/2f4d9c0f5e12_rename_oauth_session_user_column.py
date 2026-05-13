"""rename oauth session user column

Revision ID: 2f4d9c0f5e12
Revises: d5238feded44
Create Date: 2026-05-13 20:55:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2f4d9c0f5e12'
down_revision: Union[str, Sequence[str], None] = 'd5238feded44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('oauth_sessions', 'telegram_user_id', new_column_name='user_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('oauth_sessions', 'user_id', new_column_name='telegram_user_id')
