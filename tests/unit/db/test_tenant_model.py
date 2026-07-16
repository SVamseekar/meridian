import uuid

from meridian.db.models.tenant import Tenant


def test_tenant_has_expected_columns():
    columns = {c.name for c in Tenant.__table__.columns}
    assert columns == {"id", "name", "created_at"}


def test_tenant_id_is_primary_key():
    pk_columns = [c.name for c in Tenant.__table__.primary_key.columns]
    assert pk_columns == ["id"]


def test_tenant_instantiation():
    t = Tenant(id=uuid.uuid4(), name="Acme Corp")
    assert t.name == "Acme Corp"
