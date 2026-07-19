import logging
import os
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.api.schemas.hubspot_oauth import HubSpotConnectionStatus
from meridian.api.session import get_current_tenant
from meridian.db.models.tenant_credentials import TenantCredentials
from meridian.db.session import get_async_session
from meridian.integrations.hubspot.credentials import upsert_hubspot_credentials
from meridian.integrations.hubspot.oauth import (
    HUBSPOT_SCOPES,
    HubSpotTokenExchangeError,
    build_authorize_url,
    exchange_code_for_tokens,
    fetch_portal_id,
)
from meridian.integrations.hubspot.state import (
    InvalidOAuthStateError,
    create_oauth_state_token,
    decode_oauth_state_token,
)

logger = logging.getLogger("meridian.hubspot")

hubspot_oauth_router = APIRouter(prefix="/oauth/hubspot", tags=["hubspot-oauth"])


def _frontend_integrations_url() -> str:
    base = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3001")
    return f"{base}/settings/integrations"


@hubspot_oauth_router.get("/authorize")
async def authorize(tenant_id: uuid.UUID = Depends(get_current_tenant)) -> RedirectResponse:
    logger.info('{"event": "hubspot_oauth_authorize_initiated", "tenant_id": "%s"}', tenant_id)
    state = create_oauth_state_token(tenant_id)
    return RedirectResponse(url=build_authorize_url(state))


@hubspot_oauth_router.get("/callback")
async def callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_async_session),
) -> RedirectResponse:
    try:
        tenant_id = decode_oauth_state_token(state)
    except InvalidOAuthStateError:
        logger.warning('{"event": "hubspot_oauth_callback_invalid_state"}')
        return RedirectResponse(url=f"{_frontend_integrations_url()}?error=invalid_state")

    try:
        tokens = await exchange_code_for_tokens(code)
        portal_id = await fetch_portal_id(tokens.access_token)
    except HubSpotTokenExchangeError:
        logger.warning(
            '{"event": "hubspot_oauth_callback_token_exchange_failed", "tenant_id": "%s"}', tenant_id
        )
        return RedirectResponse(url=f"{_frontend_integrations_url()}?error=token_exchange_failed")

    await upsert_hubspot_credentials(
        session, tenant_id, tokens, portal_id=portal_id, scopes=HUBSPOT_SCOPES
    )
    await session.commit()

    logger.info('{"event": "hubspot_oauth_callback_success", "tenant_id": "%s"}', tenant_id)
    return RedirectResponse(url=f"{_frontend_integrations_url()}?connected=1")


@hubspot_oauth_router.get("/status", response_model=HubSpotConnectionStatus)
async def status(
    tenant_id: uuid.UUID = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> HubSpotConnectionStatus:
    row = (
        await session.execute(
            select(TenantCredentials).where(
                TenantCredentials.tenant_id == tenant_id, TenantCredentials.provider == "hubspot"
            )
        )
    ).scalar_one_or_none()

    if row is None:
        return HubSpotConnectionStatus(connected=False, connected_at=None)
    return HubSpotConnectionStatus(connected=True, connected_at=row.updated_at)
