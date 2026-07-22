import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.db.models.tenant_credentials import TenantCredentials
from meridian.integrations.hubspot.config import (
    DEFAULT_HUBSPOT_SCOPES,
    get_hubspot_client_id,
    get_hubspot_client_secret,
    get_hubspot_redirect_uri,
)
from meridian.integrations.hubspot.credentials import (
    get_decrypted_access_token,
    get_decrypted_refresh_token,
    upsert_hubspot_credentials,
)

logger = logging.getLogger(__name__)

HUBSPOT_AUTHORIZE_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_TOKEN_INFO_URL = "https://api.hubapi.com/oauth/v1/access-tokens/{token}"
HUBSPOT_API_BASE_URL = "https://api.hubapi.com"

TOKEN_REFRESH_BUFFER_MINUTES = 5


class HubSpotAPIError(Exception):
    """Raised when a request to HubSpot API fails."""


def build_authorize_url(
    state: str,
    client_id: str | None = None,
    redirect_uri: str | None = None,
    scopes: list[str] | None = None,
) -> str:
    """Build the URL to redirect the user to HubSpot for authorization."""
    cid = client_id or get_hubspot_client_id()
    r_uri = redirect_uri or get_hubspot_redirect_uri()
    scope_list = scopes or DEFAULT_HUBSPOT_SCOPES
    scope_str = " ".join(scope_list)

    params = {
        "client_id": cid,
        "redirect_uri": r_uri,
        "scope": scope_str,
        "state": state,
    }
    return f"{HUBSPOT_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Exchange authorization code for access & refresh tokens."""
    cid = client_id or get_hubspot_client_id()
    csecret = client_secret or get_hubspot_client_secret()
    r_uri = redirect_uri or get_hubspot_redirect_uri()

    data = {
        "grant_type": "authorization_code",
        "client_id": cid,
        "client_secret": csecret,
        "redirect_uri": r_uri,
        "code": code,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    should_close = False
    if client is None:
        client = httpx.AsyncClient()
        should_close = True

    try:
        response = await client.post(HUBSPOT_TOKEN_URL, data=data, headers=headers)
        if response.status_code != 200:
            raise HubSpotAPIError(
                f"HubSpot token exchange failed ({response.status_code})"
            )
        return response.json()
    except httpx.HTTPError as exc:
        raise HubSpotAPIError(f"HTTP request to HubSpot failed: {exc}") from exc
    finally:
        if should_close:
            await client.aclose()


async def refresh_access_token(
    refresh_token: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Refresh an access token using a refresh token."""
    cid = client_id or get_hubspot_client_id()
    csecret = client_secret or get_hubspot_client_secret()

    data = {
        "grant_type": "refresh_token",
        "client_id": cid,
        "client_secret": csecret,
        "refresh_token": refresh_token,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    should_close = False
    if client is None:
        client = httpx.AsyncClient()
        should_close = True

    try:
        response = await client.post(HUBSPOT_TOKEN_URL, data=data, headers=headers)
        if response.status_code != 200:
            raise HubSpotAPIError(
                f"HubSpot token refresh failed ({response.status_code})"
            )
        return response.json()
    except httpx.HTTPError as exc:
        raise HubSpotAPIError(f"HTTP request to HubSpot failed: {exc}") from exc
    finally:
        if should_close:
            await client.aclose()


async def get_token_metadata(
    access_token: str,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Get metadata for an access token (portal ID, scopes, expiry)."""
    url = HUBSPOT_TOKEN_INFO_URL.format(token=access_token)

    should_close = False
    if client is None:
        client = httpx.AsyncClient()
        should_close = True

    try:
        response = await client.get(url)
        if response.status_code != 200:
            raise HubSpotAPIError(
                f"Failed to fetch HubSpot token metadata ({response.status_code})"
            )
        return response.json()
    except httpx.HTTPError as exc:
        raise HubSpotAPIError(f"HTTP request to HubSpot failed: {exc}") from exc
    finally:
        if should_close:
            await client.aclose()


async def ensure_fresh_token(
    credentials: TenantCredentials,
    session: AsyncSession,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Check if token is near expiration and proactive refresh if needed. Returns current valid access token."""
    now = datetime.now(timezone.utc)
    expires_at = credentials.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    buffer = timedelta(minutes=TOKEN_REFRESH_BUFFER_MINUTES)
    if expires_at - now > buffer:
        return get_decrypted_access_token(credentials)

    logger.info("HubSpot access token for tenant %s is near expiration. Refreshing...", credentials.tenant_id)
    refresh_token = get_decrypted_refresh_token(credentials)
    refreshed = await refresh_access_token(refresh_token, client=client)

    new_access_token = refreshed["access_token"]
    new_refresh_token = refreshed.get("refresh_token", refresh_token)
    expires_in = refreshed.get("expires_in", 21600)
    new_expires_at = now + timedelta(seconds=expires_in)

    await upsert_hubspot_credentials(
        session=session,
        tenant_id=credentials.tenant_id,
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_at=new_expires_at,
        hubspot_portal_id=credentials.hubspot_portal_id,
        scopes=credentials.scopes,
        commit=False,
    )

    return new_access_token


class HubSpotClient:
    """Authenticated client for reading CRM data from HubSpot API v3."""

    def __init__(self, access_token: str, client: httpx.AsyncClient | None = None):
        self.access_token = access_token
        self._external_client = client

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def list_companies(
        self, after: str | None = None, limit: int = 100
    ) -> dict:
        """Fetch a page of HubSpot company records."""
        url = f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/companies"
        params = {
            "limit": str(limit),
            "properties": "name,industry",
        }
        if after:
            params["after"] = after

        should_close = False
        client = self._external_client
        if client is None:
            client = httpx.AsyncClient()
            should_close = True

        try:
            res = await client.get(url, params=params, headers=self._get_headers())
            if res.status_code != 200:
                raise HubSpotAPIError(f"Failed to list HubSpot companies ({res.status_code})")
            return res.json()
        except httpx.HTTPError as exc:
            raise HubSpotAPIError(f"HTTP error listing companies: {exc}") from exc
        finally:
            if should_close:
                await client.aclose()

    async def list_deals(
        self, after: str | None = None, limit: int = 100
    ) -> dict:
        """Fetch a page of HubSpot deal records with company associations."""
        url = f"{HUBSPOT_API_BASE_URL}/crm/v3/objects/deals"
        params = {
            "limit": str(limit),
            "properties": "dealstage,amount,hs_lastmodifieddate,createdate",
            "associations": "companies",
        }
        if after:
            params["after"] = after

        should_close = False
        client = self._external_client
        if client is None:
            client = httpx.AsyncClient()
            should_close = True

        try:
            res = await client.get(url, params=params, headers=self._get_headers())
            if res.status_code != 200:
                raise HubSpotAPIError(f"Failed to list HubSpot deals ({res.status_code})")
            return res.json()
        except httpx.HTTPError as exc:
            raise HubSpotAPIError(f"HTTP error listing deals: {exc}") from exc
        finally:
            if should_close:
                await client.aclose()
