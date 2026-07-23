import os
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

HUBSPOT_AUTHORIZE_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"

# Decision D10 — minimal, explicit scopes only, never widened "in case they're needed later."
HUBSPOT_SCOPES = [
    "crm.objects.contacts.read",
    "crm.objects.companies.read",
    "crm.objects.companies.write",
    "crm.objects.deals.read",
]


class HubSpotTokenExchangeError(Exception):
    """Raised when HubSpot's token endpoint returns a non-200 response or a
    body that doesn't match the expected token response shape."""


@dataclass
class HubSpotTokenResponse:
    access_token: str
    refresh_token: str
    expires_in: int


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": os.environ["HUBSPOT_CLIENT_ID"],
        "redirect_uri": os.environ["HUBSPOT_REDIRECT_URI"],
        "scope": " ".join(HUBSPOT_SCOPES),
        "state": state,
    }
    return f"{HUBSPOT_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> HubSpotTokenResponse:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": os.environ["HUBSPOT_CLIENT_ID"],
                "client_secret": os.environ["HUBSPOT_CLIENT_SECRET"],
                "redirect_uri": os.environ["HUBSPOT_REDIRECT_URI"],
                "code": code,
            },
        )

    if response.status_code != 200:
        raise HubSpotTokenExchangeError(
            f"HubSpot token exchange failed with status {response.status_code}"
        )

    try:
        body = response.json()
        return HubSpotTokenResponse(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_in=body["expires_in"],
        )
    except (KeyError, ValueError) as exc:
        raise HubSpotTokenExchangeError("HubSpot token response missing expected fields") from exc


async def fetch_portal_id(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.hubapi.com/oauth/v1/access-tokens/{access_token}")

    if response.status_code != 200:
        raise HubSpotTokenExchangeError(
            f"HubSpot token-info lookup failed with status {response.status_code}"
        )

    try:
        return str(response.json()["hub_id"])
    except (KeyError, ValueError) as exc:
        raise HubSpotTokenExchangeError("HubSpot token-info response missing hub_id") from exc


async def refresh_access_token(refresh_token: str) -> HubSpotTokenResponse:
    """Exchange a refresh token for a new access/refresh token pair (D09
    proactive refresh, used by the sync worker before a tenant's token
    expires)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": os.environ["HUBSPOT_CLIENT_ID"],
                "client_secret": os.environ["HUBSPOT_CLIENT_SECRET"],
                "refresh_token": refresh_token,
            },
        )

    if response.status_code != 200:
        raise HubSpotTokenExchangeError(
            f"HubSpot token refresh failed with status {response.status_code}"
        )

    try:
        body = response.json()
        return HubSpotTokenResponse(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_in=body["expires_in"],
        )
    except (KeyError, ValueError) as exc:
        raise HubSpotTokenExchangeError("HubSpot token refresh response missing expected fields") from exc


HUBSPOT_API_BASE_URL = "https://api.hubapi.com"


class HubSpotClient:
    """Authenticated client for reading CRM data from HubSpot API v3.
    Constructed per-tenant with that tenant's decrypted access token."""

    def __init__(self, access_token: str, client: httpx.AsyncClient | None = None):
        self.access_token = access_token
        self._external_client = client

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _get(self, url: str, params: dict) -> dict:
        should_close = False
        client = self._external_client
        if client is None:
            client = httpx.AsyncClient()
            should_close = True
        try:
            response = await client.get(url, params=params, headers=self._headers())
            if response.status_code != 200:
                raise HubSpotTokenExchangeError(
                    f"HubSpot CRM read failed with status {response.status_code}"
                )
            return response.json()
        finally:
            if should_close:
                await client.aclose()

    async def list_companies(self, after: str | None = None, limit: int = 100) -> dict:
        params = {"limit": str(limit), "properties": "name,industry"}
        if after:
            params["after"] = after
        return await self._get(f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/companies", params)

    async def list_deals(self, after: str | None = None, limit: int = 100) -> dict:
        params = {
            "limit": str(limit),
            "properties": "dealstage,amount,hs_lastmodifieddate,createdate",
            "associations": "companies",
        }
        if after:
            params["after"] = after
        return await self._get(f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/deals", params)
