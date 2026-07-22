import uuid
from sqlalchemy import UniqueConstraint

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


def test_staging_hubspot_company_has_composite_unique_constraint():
    constraints = [
        c for c in StagingHubspotCompany.__table__.constraints
        if isinstance(c, UniqueConstraint) and c.name == "uq_staging_hubspot_companies_tenant_company"
    ]
    assert len(constraints) == 1
    assert [col.name for col in constraints[0].columns] == ["tenant_id", "hubspot_company_id"]
