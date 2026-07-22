import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.db.models.staging_hubspot_company import StagingHubspotCompany
from meridian.db.models.staging_hubspot_deal import StagingHubspotDeal

logger = logging.getLogger(__name__)


async def audit_inbound_hubspot_data(
    session: AsyncSession, tenant_id: uuid.UUID
) -> dict:
    """Audit staging_hubspot_* tables for a tenant to flag data quality issues."""
    # 1. Check for orphan deals (deals without a matching company row for this tenant)
    company_ids_stmt = select(StagingHubspotCompany.hubspot_company_id).where(
        StagingHubspotCompany.tenant_id == tenant_id
    )
    res_companies = await session.execute(company_ids_stmt)
    known_company_ids = set(res_companies.scalars().all())

    deals_stmt = select(StagingHubspotDeal).where(
        StagingHubspotDeal.tenant_id == tenant_id
    )
    res_deals = await session.execute(deals_stmt)
    tenant_deals = res_deals.scalars().all()

    orphan_deal_count = 0
    missing_field_count = 0

    for deal in tenant_deals:
        if deal.hubspot_company_id not in known_company_ids:
            orphan_deal_count += 1
            logger.warning(
                "Audit flag: Orphan deal detected tenant_id=%s deal_id=%s company_id=%s",
                tenant_id,
                deal.hubspot_deal_id,
                deal.hubspot_company_id,
            )
        if not deal.stage or deal.amount is None:
            missing_field_count += 1
            logger.warning(
                "Audit flag: Deal missing required fields tenant_id=%s deal_id=%s",
                tenant_id,
                deal.hubspot_deal_id,
            )

    summary = {
        "tenant_id": str(tenant_id),
        "orphan_deals": orphan_deal_count,
        "missing_fields": missing_field_count,
    }
    logger.info("HubSpot sync audit completed for tenant %s: %s", tenant_id, summary)
    return summary
