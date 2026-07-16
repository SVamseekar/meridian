import uuid
from datetime import datetime, timezone

import pytest

from meridian.api.write_keys import generate_write_key
from meridian.db.models.tenant import Tenant
from meridian.db.models.tenant_write_key import TenantWriteKey
from meridian.db.models.raw_event import RawEvent


@pytest.mark.asyncio
async def test_valid_write_key_returns_202_and_lands_row(async_client, db_session):
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant")
    db_session.add(tenant)
    await db_session.flush()

    plaintext, key_hash = generate_write_key()
    db_session.add(TenantWriteKey(id=uuid.uuid4(), tenant_id=tenant.id, write_key_hash=key_hash))
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/telemetry/event",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={
            "anonymous_id": "anon-123",
            "event_name": "login",
            "properties": {"firm_type": "boutique"},
            "client_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}

    from sqlalchemy import select
    result = await db_session.execute(select(RawEvent).where(RawEvent.tenant_id == tenant.id))
    row = result.scalar_one()
    assert row.event_name == "login"
    assert row.anonymous_id == "anon-123"


@pytest.mark.asyncio
async def test_missing_auth_header_returns_401(async_client):
    response = await async_client.post(
        "/api/v1/telemetry/event",
        json={
            "anonymous_id": "anon-123",
            "event_name": "login",
            "properties": {},
            "client_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_write_key_returns_401(async_client):
    response = await async_client.post(
        "/api/v1/telemetry/event",
        headers={"Authorization": "Bearer wk_live_doesnotexist"},
        json={
            "anonymous_id": "anon-123",
            "event_name": "login",
            "properties": {},
            "client_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_revoked_write_key_returns_401(async_client, db_session):
    from datetime import datetime as dt

    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant 2")
    db_session.add(tenant)
    await db_session.flush()

    plaintext, key_hash = generate_write_key()
    db_session.add(
        TenantWriteKey(
            id=uuid.uuid4(), tenant_id=tenant.id, write_key_hash=key_hash,
            revoked_at=dt.now(timezone.utc),
        )
    )
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/telemetry/event",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={
            "anonymous_id": "anon-123",
            "event_name": "login",
            "properties": {},
            "client_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_client_supplied_tenant_id_is_ignored(async_client, db_session):
    tenant = Tenant(id=uuid.uuid4(), name="Real Tenant")
    other_tenant_id = str(uuid.uuid4())
    db_session.add(tenant)
    await db_session.flush()

    plaintext, key_hash = generate_write_key()
    db_session.add(TenantWriteKey(id=uuid.uuid4(), tenant_id=tenant.id, write_key_hash=key_hash))
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/telemetry/event",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={
            "tenant_id": other_tenant_id,
            "anonymous_id": "anon-123",
            "event_name": "login",
            "properties": {},
            "client_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 202

    from sqlalchemy import select
    result = await db_session.execute(select(RawEvent).where(RawEvent.anonymous_id == "anon-123"))
    row = result.scalar_one()
    assert str(row.tenant_id) == str(tenant.id)
    assert str(row.tenant_id) != other_tenant_id


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429(async_client, db_session, monkeypatch):
    tenant = Tenant(id=uuid.uuid4(), name="Rate Limited Tenant")
    db_session.add(tenant)
    await db_session.flush()

    plaintext, key_hash = generate_write_key()
    db_session.add(TenantWriteKey(id=uuid.uuid4(), tenant_id=tenant.id, write_key_hash=key_hash))
    await db_session.commit()

    from meridian.api.routes import telemetry as telemetry_module
    monkeypatch.setattr(telemetry_module, "TELEMETRY_RATE_LIMIT", 1)

    body = {
        "anonymous_id": "anon-123",
        "event_name": "login",
        "properties": {},
        "client_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    headers = {"Authorization": f"Bearer {plaintext}"}

    first = await async_client.post("/api/v1/telemetry/event", headers=headers, json=body)
    assert first.status_code == 202

    second = await async_client.post("/api/v1/telemetry/event", headers=headers, json=body)
    assert second.status_code == 429
