from meridian.db.models.raw_event import RawEvent


def test_raw_event_has_expected_columns():
    columns = {c.name for c in RawEvent.__table__.columns}
    assert columns == {
        "id", "tenant_id", "anonymous_id", "user_id",
        "event_name", "properties", "client_timestamp", "received_at",
    }


def test_raw_event_tenant_id_is_not_nullable():
    col = RawEvent.__table__.columns["tenant_id"]
    assert col.nullable is False


def test_raw_event_tenant_id_is_indexed():
    assert any(
        "tenant_id" in idx.columns.keys() for idx in RawEvent.__table__.indexes
    ) or RawEvent.__table__.columns["tenant_id"].index is True


def test_raw_event_user_id_is_nullable():
    col = RawEvent.__table__.columns["user_id"]
    assert col.nullable is True
