"""composite unique staging hubspot

Revision ID: d8cd107be2fc
Revises: de4ad7a3110e
Create Date: 2026-07-22 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8cd107be2fc'
down_revision: Union[str, None] = 'de4ad7a3110e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The FK from staging_hubspot_deals.hubspot_company_id to
    # staging_hubspot_companies.hubspot_company_id is backed by the unique
    # index being dropped below; it must go first or Postgres refuses to
    # drop the index (DependentObjectsStillExist). The FK is not recreated
    # here — deal-to-company association is now app-level only (see
    # audit.py's orphan check), matching the ORM model, which no longer
    # declares this relationship since hubspot_company_id is no longer
    # globally unique.
    op.drop_constraint(
        'staging_hubspot_deals_hubspot_company_id_fkey',
        'staging_hubspot_deals',
        type_='foreignkey',
    )

    # Remove global unique index on staging_hubspot_companies.hubspot_company_id
    op.drop_index('ix_staging_hubspot_companies_hubspot_company_id', table_name='staging_hubspot_companies')
    op.create_index('ix_staging_hubspot_companies_hubspot_company_id', 'staging_hubspot_companies', ['hubspot_company_id'], unique=False)
    op.create_unique_constraint('uq_staging_hubspot_companies_tenant_company', 'staging_hubspot_companies', ['tenant_id', 'hubspot_company_id'])

    # Remove global unique index on staging_hubspot_deals.hubspot_deal_id
    op.drop_index('ix_staging_hubspot_deals_hubspot_deal_id', table_name='staging_hubspot_deals')
    op.create_index('ix_staging_hubspot_deals_hubspot_deal_id', 'staging_hubspot_deals', ['hubspot_deal_id'], unique=False)
    op.create_unique_constraint('uq_staging_hubspot_deals_tenant_deal', 'staging_hubspot_deals', ['tenant_id', 'hubspot_deal_id'])


def downgrade() -> None:
    # NOTE: if any tenant data was ingested under the composite-unique regime
    # with hubspot_company_id/hubspot_deal_id values that collide across
    # tenants (legal post-upgrade, illegal pre-upgrade), the unique index
    # creation below will fail with a uniqueness violation. That data must be
    # deduplicated/reconciled manually before downgrading past this revision.
    op.drop_constraint('uq_staging_hubspot_deals_tenant_deal', 'staging_hubspot_deals', type_='unique')
    op.drop_index('ix_staging_hubspot_deals_hubspot_deal_id', table_name='staging_hubspot_deals')
    op.create_index('ix_staging_hubspot_deals_hubspot_deal_id', 'staging_hubspot_deals', ['hubspot_deal_id'], unique=True)

    op.drop_constraint('uq_staging_hubspot_companies_tenant_company', 'staging_hubspot_companies', type_='unique')
    op.drop_index('ix_staging_hubspot_companies_hubspot_company_id', table_name='staging_hubspot_companies')
    op.create_index('ix_staging_hubspot_companies_hubspot_company_id', 'staging_hubspot_companies', ['hubspot_company_id'], unique=True)

    op.create_foreign_key(
        'staging_hubspot_deals_hubspot_company_id_fkey',
        'staging_hubspot_deals',
        'staging_hubspot_companies',
        ['hubspot_company_id'],
        ['hubspot_company_id'],
    )
