import uuid
from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint

from meridian.db.models.staging_hubspot_deal import StagingHubspotDeal


def test_staging_hubspot_deal_has_expected_columns():
    row = StagingHubspotDeal(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        hubspot_deal_id="hs-deal-1",
        hubspot_company_id="hs-co-1",
        stage="closed_won",
        amount=25000,
        entered_stage_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert row.stage == "closed_won"
    assert row.amount == 25000


def test_staging_hubspot_deal_tenant_id_is_not_nullable():
    column = StagingHubspotDeal.__table__.columns["tenant_id"]
    assert column.nullable is False


def test_staging_hubspot_deal_has_composite_unique_constraint():
    constraints = [
        c for c in StagingHubspotDeal.__table__.constraints
        if isinstance(c, UniqueConstraint) and c.name == "uq_staging_hubspot_deals_tenant_deal"
    ]
    assert len(constraints) == 1
    assert [col.name for col in constraints[0].columns] == ["tenant_id", "hubspot_deal_id"]
