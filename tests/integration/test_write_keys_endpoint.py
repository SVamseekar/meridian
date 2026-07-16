import uuid

import pytest

from meridian.db.models.tenant import Tenant
from scripts.seed_dev_tenant import DEV_TENANT_ID


@pytest.mark.asyncio
async def test_create_write_key_returns_plaintext_once(async_client, db_session):
    tenant = Tenant(id=DEV_TENANT_ID, name="Dev Tenant")
    db_session.add(tenant)
    await db_session.commit()

    response = await async_client.post(f"/api/v1/tenants/{DEV_TENANT_ID}/write-keys")
    assert response.status_code == 201
    body = response.json()
    assert body["key"].startswith("wk_live_")
    assert "id" in body and "created_at" in body


@pytest.mark.asyncio
async def test_list_write_keys_returns_masked_only(async_client, db_session):
    tenant = Tenant(id=DEV_TENANT_ID, name="Dev Tenant")
    db_session.add(tenant)
    await db_session.commit()

    create_resp = await async_client.post(f"/api/v1/tenants/{DEV_TENANT_ID}/write-keys")
    plaintext = create_resp.json()["key"]

    list_resp = await async_client.get(f"/api/v1/tenants/{DEV_TENANT_ID}/write-keys")
    assert list_resp.status_code == 200
    keys = list_resp.json()
    assert len(keys) == 1
    assert "masked_key" in keys[0]
    assert plaintext not in keys[0]["masked_key"]
    assert keys[0]["masked_key"].endswith(plaintext[-4:])


@pytest.mark.asyncio
async def test_revoke_write_key_sets_revoked_at(async_client, db_session):
    tenant = Tenant(id=DEV_TENANT_ID, name="Dev Tenant")
    db_session.add(tenant)
    await db_session.commit()

    create_resp = await async_client.post(f"/api/v1/tenants/{DEV_TENANT_ID}/write-keys")
    key_id = create_resp.json()["id"]

    revoke_resp = await async_client.delete(f"/api/v1/tenants/{DEV_TENANT_ID}/write-keys/{key_id}")
    assert revoke_resp.status_code == 204

    list_resp = await async_client.get(f"/api/v1/tenants/{DEV_TENANT_ID}/write-keys")
    keys = list_resp.json()
    assert keys[0]["revoked_at"] is not None


@pytest.mark.asyncio
async def test_wrong_tenant_id_returns_404(async_client):
    other_id = uuid.uuid4()
    response = await async_client.post(f"/api/v1/tenants/{other_id}/write-keys")
    assert response.status_code == 404
