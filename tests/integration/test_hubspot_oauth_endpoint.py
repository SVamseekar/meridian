import uuid

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from meridian.api.session import create_session_token
from meridian.crypto import decrypt_secret
from meridian.db.models.tenant import Tenant
from meridian.db.models.tenant_credentials import TenantCredentials
from meridian.integrations.hubspot.state import create_oauth_state_token


async def _authed_client(async_client, db_session, tenant_id=None):
    tenant_id = tenant_id or uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Dev Tenant"))
    await db_session.commit()
    async_client.cookies.set("meridian_session", create_session_token(tenant_id))
    return tenant_id


@pytest.mark.asyncio
async def test_authorize_requires_session(async_client):
    response = await async_client.get("/api/v1/oauth/hubspot/authorize", follow_redirects=False)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authorize_redirects_to_hubspot_with_state(async_client, db_session, monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/hubspot/callback")
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-state-secret")
    await _authed_client(async_client, db_session)

    response = await async_client.get("/api/v1/oauth/hubspot/authorize", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://app.hubspot.com/oauth/authorize")
    assert "state=" in response.headers["location"]


@pytest.mark.asyncio
async def test_callback_rejects_invalid_state(async_client, monkeypatch):
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-state-secret")

    response = await async_client.get(
        "/api/v1/oauth/hubspot/callback",
        params={"code": "irrelevant", "state": "garbage-state"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert "error=" in response.headers["location"]


@pytest.mark.asyncio
async def test_callback_exchanges_code_and_stores_encrypted_credentials(
    async_client, db_session, monkeypatch
):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/hubspot/callback")
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-state-secret")
    tenant_id = await _authed_client(async_client, db_session)
    state = create_oauth_state_token(tenant_id)

    real_post = httpx.AsyncClient.post
    real_get = httpx.AsyncClient.get

    async def _mock_post(self, url, data=None, **kwargs):
        if str(url) == "https://api.hubapi.com/oauth/v1/token":
            return httpx.Response(
                200,
                json={"access_token": "hs-access", "refresh_token": "hs-refresh", "expires_in": 1800},
                request=httpx.Request("POST", url),
            )
        return await real_post(self, url, data=data, **kwargs)

    async def _mock_get(self, url, **kwargs):
        if str(url).startswith("https://api.hubapi.com/oauth/v1/access-tokens/"):
            return httpx.Response(200, json={"hub_id": 999999}, request=httpx.Request("GET", url))
        return await real_get(self, url, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)

    response = await async_client.get(
        "/api/v1/oauth/hubspot/callback",
        params={"code": "test-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert "connected=1" in response.headers["location"]

    result = await db_session.execute(
        select(TenantCredentials).where(
            TenantCredentials.tenant_id == tenant_id, TenantCredentials.provider == "hubspot"
        )
    )
    row = result.scalar_one()
    assert row.hubspot_portal_id == "999999"
    assert decrypt_secret(row.access_token_encrypted) == "hs-access"


@pytest.mark.asyncio
async def test_status_returns_not_connected_when_no_row_exists(async_client, db_session):
    await _authed_client(async_client, db_session)

    response = await async_client.get("/api/v1/oauth/hubspot/status")

    assert response.status_code == 200
    assert response.json() == {"connected": False, "connected_at": None}


@pytest.mark.asyncio
async def test_status_returns_connected_after_credentials_stored(async_client, db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = await _authed_client(async_client, db_session)

    from meridian.integrations.hubspot.credentials import upsert_hubspot_credentials
    from meridian.integrations.hubspot.oauth import HubSpotTokenResponse

    await upsert_hubspot_credentials(
        db_session,
        tenant_id,
        HubSpotTokenResponse(access_token="a", refresh_token="b", expires_in=1800),
        portal_id="12345",
        scopes=["crm.objects.deals.read"],
    )
    await db_session.commit()

    response = await async_client.get("/api/v1/oauth/hubspot/status")

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["connected_at"] is not None
