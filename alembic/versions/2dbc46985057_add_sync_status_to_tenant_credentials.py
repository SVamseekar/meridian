"""add sync status tracking to tenant_credentials

Revision ID: 2dbc46985057
Revises: e7f8901234ab
Create Date: 2026-07-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2dbc46985057'
down_revision: Union[str, None] = 'e7f8901234ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tenant_credentials',
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'tenant_credentials',
        sa.Column('last_sync_status', sa.String(), nullable=True),
    )
    op.add_column(
        'tenant_credentials',
        sa.Column('last_sync_error', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('tenant_credentials', 'last_sync_error')
    op.drop_column('tenant_credentials', 'last_sync_status')
    op.drop_column('tenant_credentials', 'last_sync_at')
