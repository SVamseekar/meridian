import uuid

from meridian.db.models.identity_map import IdentityMap


def test_identity_map_has_expected_columns():
    row = IdentityMap(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        anonymous_id="anon-123",
        user_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
    )
    assert row.anonymous_id == "anon-123"


def test_identity_map_tenant_id_is_not_nullable():
    column = IdentityMap.__table__.columns["tenant_id"]
    assert column.nullable is False


def test_identity_map_anonymous_id_is_not_nullable():
    column = IdentityMap.__table__.columns["anonymous_id"]
    assert column.nullable is False


def test_identity_map_account_id_is_not_nullable():
    column = IdentityMap.__table__.columns["account_id"]
    assert column.nullable is False
