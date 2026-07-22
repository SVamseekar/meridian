import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.db.models.staging_hubspot_company import StagingHubspotCompany
from meridian.db.models.staging_hubspot_deal import StagingHubspotDeal
from meridian.integrations.hubspot.audit import audit_inbound_hubspot_data
from meridian.integrations.hubspot.client import HubSpotClient, ensure_fresh_token
from meridian.integrations.hubspot.credentials import (
    get_hubspot_credentials,
    record_hubspot_sync_result,
)

logger = logging.getLogger(__name__)

# Hard cap on pages fetched per entity per sync pass. Guards against a
# malformed or repeating `paging.next.after` cursor turning into an infinite
# loop; 10,000 pages at limit=100 is 1M records, far beyond what a single
# tenant should have, so this is a safety backstop, not a real-world limit.
MAX_SYNC_PAGES = 10_000


def _parse_datetime(dt_str: str | None) -> datetime:
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        # Handle ISO strings like 2026-07-22T10:00:00Z or milliseconds format
        clean_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except ValueError:
        return datetime.now(timezone.utc)


async def _fetch_existing_deals(
    session: AsyncSession, tenant_id: uuid.UUID, deal_ids: list[str]
) -> dict[str, StagingHubspotDeal]:
    """Batch-fetch existing deal rows for a page of deal IDs in one query,
    instead of one SELECT per deal."""
    if not deal_ids:
        return {}
    res = await session.execute(
        select(StagingHubspotDeal).where(
            StagingHubspotDeal.tenant_id == tenant_id,
            StagingHubspotDeal.hubspot_deal_id.in_(deal_ids),
        )
    )
    return {row.hubspot_deal_id: row for row in res.scalars().all()}


async def upsert_deal_from_properties(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    deal_id: str,
    stage: str | None,
    amount: object,
    entered_stage_at: datetime | None = None,
    hubspot_company_id: str | None = None,
    existing: StagingHubspotDeal | None = None,
) -> StagingHubspotDeal:
    """Upsert a single deal row from a partial or full set of HubSpot
    properties. Shared by the polling sync (full property set from a CRM
    read) and the webhook handler (partial set from a single property-change
    event), so both ingestion paths populate/update the same fields the same
    way instead of diverging.

    Pass `existing` when the caller has already batch-fetched it (see
    `_fetch_existing_deals`) to avoid a per-item SELECT; omit it (as the
    webhook handler does, one event at a time) to look it up here."""
    try:
        parsed_amount = int(float(amount)) if amount not in (None, "") else 0
    except (ValueError, TypeError):
        parsed_amount = 0

    if existing is None:
        res = await session.execute(
            select(StagingHubspotDeal).where(
                StagingHubspotDeal.tenant_id == tenant_id,
                StagingHubspotDeal.hubspot_deal_id == deal_id,
            )
        )
        existing = res.scalar_one_or_none()

    if existing is None:
        row = StagingHubspotDeal(
            tenant_id=tenant_id,
            hubspot_deal_id=deal_id,
            hubspot_company_id=hubspot_company_id or "orphan",
            stage=stage or "unknown",
            amount=parsed_amount,
            entered_stage_at=entered_stage_at or datetime.now(timezone.utc),
        )
        session.add(row)
        return row

    if stage is not None:
        existing.stage = stage
    if amount not in (None, ""):
        existing.amount = parsed_amount
    if entered_stage_at is not None:
        existing.entered_stage_at = entered_stage_at
    if hubspot_company_id is not None:
        existing.hubspot_company_id = hubspot_company_id
    return existing


async def sync_tenant_inbound(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    client: HubSpotClient | None = None,
) -> dict:
    """Run inbound polling sync pass for a single tenant."""
    logger.info("Starting HubSpot inbound sync for tenant %s", tenant_id)
    credentials = await get_hubspot_credentials(session, tenant_id)
    if credentials is None:
        logger.info("Tenant %s is not connected to HubSpot. Skipping sync.", tenant_id)
        return {"tenant_id": str(tenant_id), "status": "skipped_not_connected"}

    owns_http_client = False
    http_client: httpx.AsyncClient | None = None
    try:
        access_token = await ensure_fresh_token(credentials, session)
        if client is None:
            # Share one httpx connection across every paginated page fetch in
            # this sync pass instead of opening/closing a fresh TCP+TLS
            # connection per page.
            http_client = httpx.AsyncClient()
            owns_http_client = True
            client = HubSpotClient(access_token=access_token, client=http_client)

        # 1. Sync Companies
        companies_upserted = 0
        after_company = None
        seen_company_cursors: set[str] = set()
        for _ in range(MAX_SYNC_PAGES):
            data = await client.list_companies(after=after_company)
            results = data.get("results", [])

            page_company_ids = [str(item["id"]) for item in results]
            existing_companies: dict[str, StagingHubspotCompany] = {}
            if page_company_ids:
                res = await session.execute(
                    select(StagingHubspotCompany).where(
                        StagingHubspotCompany.tenant_id == tenant_id,
                        StagingHubspotCompany.hubspot_company_id.in_(page_company_ids),
                    )
                )
                existing_companies = {
                    row.hubspot_company_id: row for row in res.scalars().all()
                }

            for item in results:
                company_id = str(item["id"])
                props = item.get("properties", {})
                name = props.get("name") or "Unnamed Company"
                firm_type = props.get("industry") or "unknown"

                existing = existing_companies.get(company_id)
                if existing is None:
                    row = StagingHubspotCompany(
                        tenant_id=tenant_id,
                        hubspot_company_id=company_id,
                        name=name,
                        firm_type=firm_type,
                    )
                    session.add(row)
                else:
                    existing.name = name
                    existing.firm_type = firm_type
                companies_upserted += 1

            paging = data.get("paging", {})
            next_page = paging.get("next", {})
            after_company = next_page.get("after")
            if not after_company:
                break
            if after_company in seen_company_cursors:
                logger.warning(
                    "HubSpot company pagination returned a repeated cursor for tenant %s; stopping early",
                    tenant_id,
                )
                break
            seen_company_cursors.add(after_company)
        else:
            logger.warning(
                "HubSpot company pagination for tenant %s hit the %d-page safety cap; stopping early",
                tenant_id,
                MAX_SYNC_PAGES,
            )

        # 2. Sync Deals
        deals_upserted = 0
        after_deal = None
        seen_deal_cursors: set[str] = set()
        for _ in range(MAX_SYNC_PAGES):
            data = await client.list_deals(after=after_deal)
            results = data.get("results", [])

            page_deal_ids = [str(item["id"]) for item in results]
            existing_deals = await _fetch_existing_deals(session, tenant_id, page_deal_ids)

            for item in results:
                deal_id = str(item["id"])
                props = item.get("properties", {})

                # Resolve associated company ID
                associated_company_id = "orphan"
                associations = item.get("associations", {})
                companies_assoc = associations.get("companies", {})
                assoc_results = companies_assoc.get("results", [])
                if assoc_results:
                    associated_company_id = str(assoc_results[0]["id"])

                await upsert_deal_from_properties(
                    session=session,
                    tenant_id=tenant_id,
                    deal_id=deal_id,
                    stage=props.get("dealstage"),
                    amount=props.get("amount"),
                    entered_stage_at=_parse_datetime(
                        props.get("hs_lastmodifieddate") or props.get("createdate")
                    ),
                    hubspot_company_id=associated_company_id,
                    existing=existing_deals.get(deal_id),
                )
                deals_upserted += 1

            paging = data.get("paging", {})
            next_page = paging.get("next", {})
            after_deal = next_page.get("after")
            if not after_deal:
                break
            if after_deal in seen_deal_cursors:
                logger.warning(
                    "HubSpot deal pagination returned a repeated cursor for tenant %s; stopping early",
                    tenant_id,
                )
                break
            seen_deal_cursors.add(after_deal)
        else:
            logger.warning(
                "HubSpot deal pagination for tenant %s hit the %d-page safety cap; stopping early",
                tenant_id,
                MAX_SYNC_PAGES,
            )

        await session.commit()

        # 3. Audit check
        audit_summary = await audit_inbound_hubspot_data(session, tenant_id)

        await record_hubspot_sync_result(session, tenant_id, status="success")

        summary = {
            "tenant_id": str(tenant_id),
            "status": "success",
            "companies_upserted": companies_upserted,
            "deals_upserted": deals_upserted,
            "audit": audit_summary,
        }
        logger.info("Completed HubSpot sync for tenant %s: %s", tenant_id, summary)
        return summary

    except Exception as exc:
        await session.rollback()
        logger.error("HubSpot sync failed for tenant %s: %s", tenant_id, exc, exc_info=True)
        await record_hubspot_sync_result(session, tenant_id, status="failed", error=str(exc))
        return {
            "tenant_id": str(tenant_id),
            "status": "failed",
            "error": str(exc),
        }
    finally:
        if owns_http_client and http_client is not None:
            await http_client.aclose()
