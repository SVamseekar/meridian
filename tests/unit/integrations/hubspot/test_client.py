import httpx
import pytest

from meridian.integrations.hubspot.client import (
    HubSpotAPIError,
    HubSpotClient,
    build_authorize_url,
    exchange_code_for_tokens,
    get_token_metadata,
    refresh_access_token,
)


def test_build_authorize_url_formatting(monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv(
        "HUBSPOT_REDIRECT_URI",
        "http://localhost:8000/api/v1/oauth/hubspot/callback",
    )

    url = build_authorize_url(state="my-state-token")

    assert "https://app.hubspot.com/oauth/authorize?" in url
    assert "client_id=test-client-id" in url
    assert "state=my-state-token" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Foauth%2Fhubspot%2Fcallback" in url
    assert "scope=" in url


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_success(monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "client-123")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "secret-456")

    async def mock_handler(request: httpx.Request):
        assert request.url == "https://api.hubapi.com/oauth/v1/token"
        assert b"grant_type=authorization_code" in request.content
        assert b"code=test-code" in request.content
        return httpx.Response(
            200,
            json={
                "access_token": "acc_123",
                "refresh_token": "ref_456",
                "expires_in": 21600,
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await exchange_code_for_tokens("test-code", client=client)

    assert res["access_token"] == "acc_123"
    assert res["refresh_token"] == "ref_456"


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_error_status(monkeypatch):
    async def mock_handler(request: httpx.Request):
        return httpx.Response(400, json={"message": "BAD_CODE"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(HubSpotAPIError, match=r"HubSpot token exchange failed \(400\)"):
            await exchange_code_for_tokens("invalid-code", client=client)


@pytest.mark.asyncio
async def test_refresh_access_token_success(monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "client-123")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "secret-456")

    async def mock_handler(request: httpx.Request):
        assert request.url == "https://api.hubapi.com/oauth/v1/token"
        assert b"grant_type=refresh_token" in request.content
        assert b"refresh_token=ref_123" in request.content
        return httpx.Response(
            200,
            json={
                "access_token": "acc_new_999",
                "refresh_token": "ref_new_999",
                "expires_in": 21600,
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await refresh_access_token("ref_123", client=client)

    assert res["access_token"] == "acc_new_999"


@pytest.mark.asyncio
async def test_get_token_metadata_success():
    async def mock_handler(request: httpx.Request):
        assert "access-tokens/acc_123" in str(request.url)
        return httpx.Response(
            200,
            json={
                "hub_id": 98765,
                "user": "user@example.com",
                "scopes": ["companies.read", "deals.read"],
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await get_token_metadata("acc_123", client=client)

    assert res["hub_id"] == 98765
    assert res["scopes"] == ["companies.read", "deals.read"]


@pytest.mark.asyncio
async def test_hubspot_client_list_companies():
    async def mock_handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer test_acc_token"
        assert "/crm/v3/objects/companies" in str(request.url)
        return httpx.Response(
            200,
            json={
                "results": [
                    {"id": "comp_1", "properties": {"name": "Acme Corp", "industry": "Technology"}}
                ],
                "paging": {"next": {"after": "cursor_123"}},
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        hs_client = HubSpotClient("test_acc_token", client=http_client)
        data = await hs_client.list_companies()

    assert len(data["results"]) == 1
    assert data["results"][0]["properties"]["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_hubspot_client_list_deals():
    async def mock_handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer test_acc_token"
        assert "/crm/v3/objects/deals" in str(request.url)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "deal_1",
                        "properties": {"dealstage": "closedwon", "amount": "50000"},
                        "associations": {
                            "companies": {
                                "results": [{"id": "comp_1", "type": "deal_to_company"}]
                            }
                        },
                    }
                ]
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        hs_client = HubSpotClient("test_acc_token", client=http_client)
        data = await hs_client.list_deals()

    assert len(data["results"]) == 1
    assert data["results"][0]["properties"]["dealstage"] == "closedwon"
