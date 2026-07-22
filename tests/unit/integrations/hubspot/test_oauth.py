import httpx
import pytest

from meridian.integrations.hubspot.oauth import (
    HUBSPOT_SCOPES,
    HubSpotClient,
    HubSpotTokenExchangeError,
    HubSpotTokenResponse,
    build_authorize_url,
    exchange_code_for_tokens,
    refresh_access_token,
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


@pytest.mark.asyncio
async def test_refresh_access_token_returns_parsed_response(monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "test-client-secret")

    async def _mock_post(self, url, data=None, **kwargs):
        assert url == "https://api.hubapi.com/oauth/v1/token"
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == "old-refresh-token"
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 21600,
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    result = await refresh_access_token("old-refresh-token")

    assert result == HubSpotTokenResponse(
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        expires_in=21600,
    )


@pytest.mark.asyncio
async def test_refresh_access_token_raises_on_non_200(monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "test-client-secret")

    async def _mock_post(self, url, data=None, **kwargs):
        return httpx.Response(401, json={"message": "invalid grant"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    with pytest.raises(HubSpotTokenExchangeError):
        await refresh_access_token("revoked-refresh-token")


@pytest.mark.asyncio
async def test_hubspot_client_list_companies_sends_bearer_token():
    async def mock_handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer test-access-token"
        assert "/crm/v3/objects/companies" in str(request.url)
        return httpx.Response(
            200,
            json={"results": [{"id": "1", "properties": {"name": "Acme", "industry": "Tech"}}]},
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HubSpotClient("test-access-token", client=http_client)
        data = await client.list_companies()

    assert data["results"][0]["properties"]["name"] == "Acme"


@pytest.mark.asyncio
async def test_hubspot_client_list_deals_sends_bearer_token():
    async def mock_handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer test-access-token"
        assert "/crm/v3/objects/deals" in str(request.url)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "1",
                        "properties": {"dealstage": "closedwon", "amount": "1000"},
                        "associations": {"companies": {"results": [{"id": "1"}]}},
                    }
                ]
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HubSpotClient("test-access-token", client=http_client)
        data = await client.list_deals()

    assert data["results"][0]["properties"]["dealstage"] == "closedwon"


@pytest.mark.asyncio
async def test_hubspot_client_raises_on_non_200():
    async def mock_handler(request: httpx.Request):
        return httpx.Response(500, json={"message": "server error"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HubSpotClient("test-access-token", client=http_client)
        with pytest.raises(HubSpotTokenExchangeError):
            await client.list_companies()
