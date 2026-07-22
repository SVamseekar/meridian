import uuid
from datetime import datetime, timezone

import pytest

from meridian.db.models.staging_hubspot_company import StagingHubspotCompany
from meridian.db.models.staging_hubspot_deal import StagingHubspotDeal
from meridian.db.models.tenant import Tenant
from meridian.integrations.hubspot.audit import audit_inbound_hubspot_data


@pytest.mark.asyncio
async def test_audit_flags_orphan_deal_with_no_matching_company(db_session):
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    db_session.add(
        StagingHubspotDeal(
            tenant_id=tenant_id,
            hubspot_deal_id="deal-1",
            hubspot_company_id="unknown-company",
            stage="closedwon",
            amount=1000,
            entered_stage_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    summary = await audit_inbound_hubspot_data(db_session, tenant_id)

    assert summary["orphan_deals"] == 1
    assert summary["missing_fields"] == 0


@pytest.mark.asyncio
async def test_audit_flags_deal_missing_required_fields(db_session):
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    db_session.add(
        StagingHubspotCompany(
            tenant_id=tenant_id, hubspot_company_id="co-1", name="Acme", firm_type="boutique"
        )
    )
    db_session.add(
        StagingHubspotDeal(
            tenant_id=tenant_id,
            hubspot_deal_id="deal-1",
            hubspot_company_id="co-1",
            stage="",
            amount=0,
            entered_stage_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    summary = await audit_inbound_hubspot_data(db_session, tenant_id)

    assert summary["orphan_deals"] == 0
    assert summary["missing_fields"] == 1


@pytest.mark.asyncio
async def test_audit_clean_data_reports_zero_flags(db_session):
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    db_session.add(
        StagingHubspotCompany(
            tenant_id=tenant_id, hubspot_company_id="co-1", name="Acme", firm_type="boutique"
        )
    )
    db_session.add(
        StagingHubspotDeal(
            tenant_id=tenant_id,
            hubspot_deal_id="deal-1",
            hubspot_company_id="co-1",
            stage="closedwon",
            amount=5000,
            entered_stage_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    summary = await audit_inbound_hubspot_data(db_session, tenant_id)

    assert summary["orphan_deals"] == 0
    assert summary["missing_fields"] == 0


@pytest.mark.asyncio
async def test_audit_scopes_to_tenant(db_session):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    db_session.add(Tenant(id=tenant_a, name="Tenant A"))
    db_session.add(Tenant(id=tenant_b, name="Tenant B"))
    await db_session.commit()

    # Tenant B has an orphan deal; tenant A has none.
    db_session.add(
        StagingHubspotDeal(
            tenant_id=tenant_b,
            hubspot_deal_id="deal-b1",
            hubspot_company_id="nonexistent",
            stage="closedwon",
            amount=1000,
            entered_stage_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    summary_a = await audit_inbound_hubspot_data(db_session, tenant_a)
    assert summary_a["orphan_deals"] == 0

    summary_b = await audit_inbound_hubspot_data(db_session, tenant_b)
    assert summary_b["orphan_deals"] == 1
