import uuid

from meridian.db.models.account import Account


def test_account_has_expected_columns():
    account = Account(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        hubspot_company_id=None,
        name="Acme Corp",
        firm_type="boutique",
        contract_value=50000,
    )
    assert account.name == "Acme Corp"
    assert account.firm_type == "boutique"
    assert account.contract_value == 50000


def test_account_tenant_id_is_not_nullable():
    column = Account.__table__.columns["tenant_id"]
    assert column.nullable is False


def test_account_tenant_id_is_indexed():
    column = Account.__table__.columns["tenant_id"]
    assert column.index is True


def test_account_hubspot_company_id_is_nullable():
    column = Account.__table__.columns["hubspot_company_id"]
    assert column.nullable is True
