import httpx
import pytest

from meridian.integrations.hubspot.oauth import (
    HUBSPOT_SCOPES,
    HubSpotTokenExchangeError,
    HubSpotTokenResponse,
    build_authorize_url,
    exchange_code_for_tokens,
)


def test_build_authorize_url_includes_client_id_redirect_and_state(monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/hubspot/callback")

    url = build_authorize_url("test-state-token")

    assert url.startswith("https://app.hubspot.com/oauth/authorize")
    assert "client_id=test-client-id" in url
    assert "state=test-state-token" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Foauth%2Fhubspot%2Fcallback" in url
    for scope in HUBSPOT_SCOPES:
        assert scope in url


def test_hubspot_scopes_match_decision_d10():
    assert HUBSPOT_SCOPES == [
        "crm.objects.contacts.read",
        "crm.objects.companies.read",
        "crm.objects.companies.write",
        "crm.objects.deals.read",
    ]


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_returns_parsed_response(monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/hubspot/callback")

    async def _mock_post(self, url, data=None, **kwargs):
        assert url == "https://api.hubapi.com/oauth/v1/token"
        assert data["grant_type"] == "authorization_code"
        assert data["code"] == "test-auth-code"
        assert data["client_id"] == "test-client-id"
        assert data["client_secret"] == "test-client-secret"
        return httpx.Response(
            200,
            json={
                "access_token": "hs-access-token",
                "refresh_token": "hs-refresh-token",
                "expires_in": 1800,
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    result = await exchange_code_for_tokens("test-auth-code")

    assert result == HubSpotTokenResponse(
        access_token="hs-access-token",
        refresh_token="hs-refresh-token",
        expires_in=1800,
    )


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_raises_on_non_200(monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/api/v1/oauth/hubspot/callback")

    async def _mock_post(self, url, data=None, **kwargs):
        return httpx.Response(
            400,
            json={"message": "invalid grant"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    with pytest.raises(HubSpotTokenExchangeError):
        await exchange_code_for_tokens("bad-code")
