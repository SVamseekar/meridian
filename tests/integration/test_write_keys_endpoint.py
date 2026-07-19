import uuid

import pytest

from meridian.api.session import create_session_token
from meridian.db.models.tenant import Tenant


async def _authed_client(async_client, db_session, tenant_id=None):
    tenant_id = tenant_id or uuid.uuid4()
    tenant = Tenant(id=tenant_id, name="Dev Tenant")
    db_session.add(tenant)
    await db_session.commit()
    token = create_session_token(tenant_id)
    async_client.cookies.set("meridian_session", token)
    return tenant_id


@pytest.mark.asyncio
async def test_create_write_key_returns_plaintext_once(async_client, db_session):
    await _authed_client(async_client, db_session)

    response = await async_client.post("/api/v1/write-keys")
    assert response.status_code == 201
    body = response.json()
    assert body["key"].startswith("wk_live_")
    assert "id" in body and "created_at" in body


@pytest.mark.asyncio
async def test_list_write_keys_returns_masked_only(async_client, db_session):
    await _authed_client(async_client, db_session)

    create_resp = await async_client.post("/api/v1/write-keys")
    plaintext = create_resp.json()["key"]

    list_resp = await async_client.get("/api/v1/write-keys")
    assert list_resp.status_code == 200
    keys = list_resp.json()
    assert len(keys) == 1
    assert "masked_key" in keys[0]
    assert plaintext not in keys[0]["masked_key"]
    assert keys[0]["masked_key"].endswith(plaintext[-4:])


@pytest.mark.asyncio
async def test_revoke_write_key_sets_revoked_at(async_client, db_session):
    await _authed_client(async_client, db_session)

    create_resp = await async_client.post("/api/v1/write-keys")
    key_id = create_resp.json()["id"]

    revoke_resp = await async_client.delete(f"/api/v1/write-keys/{key_id}")
    assert revoke_resp.status_code == 204

    list_resp = await async_client.get("/api/v1/write-keys")
    keys = list_resp.json()
    assert keys[0]["revoked_at"] is not None


@pytest.mark.asyncio
async def test_write_keys_require_session(async_client):
    # No cookie set on the function-scoped async_client fixture — must be
    # rejected before touching the DB.
    response = await async_client.post("/api/v1/write-keys")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_write_keys_are_scoped_to_session_tenant(async_client, db_session):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    db_session.add(Tenant(id=tenant_a, name="Tenant A"))
    db_session.add(Tenant(id=tenant_b, name="Tenant B"))
    await db_session.commit()

    async_client.cookies.set("meridian_session", create_session_token(tenant_a))
    await async_client.post("/api/v1/write-keys")

    async_client.cookies.set("meridian_session", create_session_token(tenant_b))
    list_resp = await async_client.get("/api/v1/write-keys")

    assert list_resp.json() == []
