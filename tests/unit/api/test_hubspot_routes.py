import uuid
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from meridian.api.session import create_session_token
from meridian.integrations.hubspot.state import create_oauth_state_token
from meridian.main import app


@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-oauth-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:3001")


@pytest.fixture
def client():
    return TestClient(app)


def test_hubspot_connect_requires_session(client):
    response = client.get("/api/v1/integrations/hubspot/connect")
    assert response.status_code == 401


def test_hubspot_connect_returns_authorize_url(client):
    tenant_id = uuid.uuid4()
    session_token = create_session_token(tenant_id)
    client.cookies.set("meridian_session", session_token)

    response = client.get("/api/v1/integrations/hubspot/connect")
    assert response.status_code == 200
    data = response.json()
    assert "authorize_url" in data
    assert "https://app.hubspot.com/oauth/authorize?" in data["authorize_url"]


def test_hubspot_status_not_connected(client, monkeypatch):
    tenant_id = uuid.uuid4()
    session_token = create_session_token(tenant_id)
    client.cookies.set("meridian_session", session_token)

    # Mock get_hubspot_credentials to return None
    import meridian.api.routes.hubspot as routes_mod

    async def mock_get_creds(session, tid):
        return None

    monkeypatch.setattr(routes_mod, "get_hubspot_credentials", mock_get_creds)

    response = client.get("/api/v1/integrations/hubspot/status")
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "connected": False,
        "hubspot_portal_id": None,
        "scopes": None,
        "connected_at": None,
        "last_sync_at": None,
        "last_sync_status": None,
        "last_sync_error": None,
    }


def test_hubspot_callback_invalid_state_redirects_with_error(client):
    response = client.get(
        "/api/v1/oauth/hubspot/callback?code=some-code&state=invalid-state",
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "http://localhost:3001/settings/hubspot?error=invalid_state"


def test_hubspot_callback_missing_state_redirects_with_error(client):
    response = client.get(
        "/api/v1/oauth/hubspot/callback?code=some-code",
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "http://localhost:3001/settings/hubspot?error=oauth_failed"


def test_hubspot_callback_successful_exchange_redirects_connected(client, monkeypatch):
    tenant_id = uuid.uuid4()
    state_token = create_oauth_state_token(tenant_id)

    import meridian.api.routes.hubspot as routes_mod

    async def mock_exchange(code):
        return {"access_token": "acc_123", "refresh_token": "ref_456", "expires_in": 3600}

    async def mock_meta(token):
        return {"hub_id": 998877, "scopes": ["companies.read"]}

    async def mock_upsert(session, tenant_id, access_token, refresh_token, expires_at, hubspot_portal_id, scopes):
        return None

    monkeypatch.setattr(routes_mod, "exchange_code_for_tokens", mock_exchange)
    monkeypatch.setattr(routes_mod, "get_token_metadata", mock_meta)
    monkeypatch.setattr(routes_mod, "upsert_hubspot_credentials", mock_upsert)

    response = client.get(
        f"/api/v1/oauth/hubspot/callback?code=valid-code&state={state_token}",
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "http://localhost:3001/settings/hubspot?connected=1"
