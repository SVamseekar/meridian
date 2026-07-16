from meridian.db.models.tenant_write_key import TenantWriteKey


def test_tenant_write_key_has_expected_columns():
    columns = {c.name for c in TenantWriteKey.__table__.columns}
    assert columns == {"id", "tenant_id", "write_key_hash", "last_four", "created_at", "revoked_at"}


def test_write_key_hash_is_unique():
    col = TenantWriteKey.__table__.columns["write_key_hash"]
    assert col.unique is True


def test_revoked_at_is_nullable():
    col = TenantWriteKey.__table__.columns["revoked_at"]
    assert col.nullable is True
