import uuid

from meridian.db.models.staging_hubspot_company import StagingHubspotCompany


def test_staging_hubspot_company_has_expected_columns():
    row = StagingHubspotCompany(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        hubspot_company_id="hs-co-1",
        name="Acme Corp",
        firm_type="boutique",
    )
    assert row.hubspot_company_id == "hs-co-1"


def test_staging_hubspot_company_tenant_id_is_not_nullable():
    column = StagingHubspotCompany.__table__.columns["tenant_id"]
    assert column.nullable is False


def test_staging_hubspot_company_hubspot_company_id_is_unique():
    column = StagingHubspotCompany.__table__.columns["hubspot_company_id"]
    assert column.unique is True
