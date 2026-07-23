"""End-to-end test for the HubSpot inbound sync worker (testing.md §6 —
scheduled/background flows need an e2e equivalent: trigger the job against
seeded data, assert the expected end state landed, not just that the
function returned without throwing)."""

import uuid

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from meridian.db.models.staging_hubspot_company import StagingHubspotCompany
from meridian.db.models.staging_hubspot_deal import StagingHubspotDeal
from meridian.db.models.tenant import Tenant
from meridian.integrations.hubspot.credentials import get_hubspot_credentials, upsert_hubspot_credentials
from meridian.integrations.hubspot.oauth import HubSpotTokenResponse
from meridian.integrations.hubspot.sync import sync_tenant_inbound


@pytest.mark.asyncio
async def test_sync_tenant_inbound_lands_companies_and_deals_from_mocked_hubspot(
    db_session, monkeypatch
):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Sync Worker Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="worker-access", refresh_token="worker-refresh", expires_in=3600)
    creds = await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="777", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    async def mock_get(self, url, params=None, headers=None, **kwargs):
        url_str = str(url)
        if "/crm/v3/objects/companies" in url_str:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "co-1", "properties": {"name": "Acme Corp", "industry": "Legal"}}
                    ]
                },
                request=httpx.Request("GET", url),
            )
        if "/crm/v3/objects/deals" in url_str:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "deal-1",
                            "properties": {
                                "dealstage": "closedwon",
                                "amount": "42000",
                                "createdate": "2026-07-01T00:00:00Z",
                            },
                            "associations": {"companies": {"results": [{"id": "co-1"}]}},
                        }
                    ]
                },
                request=httpx.Request("GET", url),
            )
        raise AssertionError(f"Unexpected URL in sync worker e2e test: {url_str}")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await sync_tenant_inbound(db_session, tenant_id)

    assert result["status"] == "success"
    assert result["companies_upserted"] == 1
    assert result["deals_upserted"] == 1
    assert result["audit"]["orphan_deals"] == 0
    assert result["audit"]["missing_fields"] == 0

    company_row = (
        await db_session.execute(
            select(StagingHubspotCompany).where(
                StagingHubspotCompany.tenant_id == tenant_id,
                StagingHubspotCompany.hubspot_company_id == "co-1",
            )
        )
    ).scalar_one()
    assert company_row.name == "Acme Corp"
    assert company_row.firm_type == "Legal"

    deal_row = (
        await db_session.execute(
            select(StagingHubspotDeal).where(
                StagingHubspotDeal.tenant_id == tenant_id,
                StagingHubspotDeal.hubspot_deal_id == "deal-1",
            )
        )
    ).scalar_one()
    assert deal_row.stage == "closedwon"
    assert deal_row.amount == 42000
    assert deal_row.hubspot_company_id == "co-1"

    # The sync also recorded a durable success signal on tenant_credentials,
    # not just a return value the caller could ignore.
    refreshed_creds = await get_hubspot_credentials(db_session, tenant_id)
    assert refreshed_creds.last_sync_status == "success"
    assert refreshed_creds.last_sync_at is not None


@pytest.mark.asyncio
async def test_sync_tenant_inbound_records_failure_when_hubspot_errors(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Failing Sync Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="acc", refresh_token="ref", expires_in=3600)
    await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="778", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    async def mock_get_error(self, url, params=None, headers=None, **kwargs):
        return httpx.Response(500, json={"message": "server error"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get_error)

    result = await sync_tenant_inbound(db_session, tenant_id)

    assert result["status"] == "failed"

    refreshed_creds = await get_hubspot_credentials(db_session, tenant_id)
    assert refreshed_creds.last_sync_status == "failed"
    assert refreshed_creds.last_sync_error is not None
