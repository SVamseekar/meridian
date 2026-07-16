"""create tenant_credentials table

Revision ID: dd416f2144bf
Revises:
Create Date: 2026-07-16

See Decision D09 in docs/guidelines/decisions.md.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "dd416f2144bf"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_credentials",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(), primary_key=True, nullable=False),
        sa.Column("hubspot_portal_id", sa.String(), nullable=True),
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_tenant_credentials_hubspot_portal_id",
        "tenant_credentials",
        ["hubspot_portal_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_credentials_hubspot_portal_id", table_name="tenant_credentials")
    op.drop_table("tenant_credentials")
