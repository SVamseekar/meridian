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
