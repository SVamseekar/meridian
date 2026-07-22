import logging
import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.api.schemas.hubspot_oauth import HubSpotConnectionStatus, HubSpotSyncStatus, HubSpotWebhookResponse
from meridian.api.session import get_current_tenant
from meridian.db.models.tenant_credentials import TenantCredentials
from meridian.db.session import get_async_session
from meridian.integrations.hubspot.credentials import (
    delete_hubspot_credentials,
    get_hubspot_credentials,
    get_tenant_by_portal_id,
    upsert_hubspot_credentials,
)
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
from meridian.integrations.hubspot.sync import upsert_deal_from_properties
from meridian.integrations.hubspot.webhooks import verify_hubspot_v3_signature

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


@hubspot_oauth_router.delete("", status_code=http_status.HTTP_204_NO_CONTENT)
async def disconnect(
    tenant_id: uuid.UUID = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Disconnect HubSpot for the current tenant."""
    await delete_hubspot_credentials(session, tenant_id)
    logger.info('{"event": "hubspot_disconnected", "tenant_id": "%s"}', tenant_id)


@hubspot_oauth_router.get("/sync-status", response_model=HubSpotSyncStatus)
async def sync_status(
    tenant_id: uuid.UUID = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_async_session),
) -> HubSpotSyncStatus:
    """Sync-health signal, separate from /status (D-DoD: a feature's
    failure modes must be observable, not just whether it's connected)."""
    creds = await get_hubspot_credentials(session, tenant_id)
    if creds is None:
        raise HTTPException(status_code=404, detail="HubSpot not connected")

    return HubSpotSyncStatus(
        hubspot_portal_id=creds.hubspot_portal_id,
        scopes=creds.scopes,
        last_sync_at=creds.last_sync_at,
        last_sync_status=creds.last_sync_status,
        last_sync_error=creds.last_sync_error,
    )


hubspot_webhook_router = APIRouter(tags=["hubspot-webhook"])


@hubspot_webhook_router.post(
    "/webhooks/hubspot",
    response_model=HubSpotWebhookResponse,
    status_code=http_status.HTTP_200_OK,
)
async def hubspot_webhook(
    request: Request,
    x_hubspot_signature_v3: str | None = Header(default=None, alias="X-HubSpot-Signature-v3"),
    x_hubspot_request_timestamp: str | None = Header(default=None, alias="X-HubSpot-Request-Timestamp"),
    session: AsyncSession = Depends(get_async_session),
) -> HubSpotWebhookResponse:
    """Public webhook ingestion endpoint for HubSpot (D10 — supplement to
    polling, tenant isolation via portalId -> tenant_credentials lookup)."""
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")
    request_uri = str(request.url)

    if not verify_hubspot_v3_signature(
        signature=x_hubspot_signature_v3,
        timestamp=x_hubspot_request_timestamp,
        method=request.method,
        uri=request_uri,
        body=body_str,
    ):
        logger.warning('{"event": "hubspot_webhook_rejected_invalid_signature"}')
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        events = await request.json()
        if not isinstance(events, list):
            events = [events]
    except Exception:
        logger.warning('{"event": "hubspot_webhook_malformed_payload"}')
        return HubSpotWebhookResponse(status="ok", processed=0)

    processed = 0
    tenants_touched: set[uuid.UUID] = set()
    for event in events:
        portal_id = str(event.get("portalId", ""))
        if not portal_id:
            continue

        creds = await get_tenant_by_portal_id(session, portal_id)
        if creds is None:
            logger.warning(
                '{"event": "hubspot_webhook_unknown_portal_id", "portal_id": "%s", '
                '"subscription_type": "%s", "object_id": "%s"}',
                portal_id,
                event.get("subscriptionType", ""),
                event.get("objectId", ""),
            )
            continue

        webhook_tenant_id = creds.tenant_id
        subscription_type = event.get("subscriptionType", "")
        object_id = str(event.get("objectId", ""))

        if subscription_type in ("deal.creation", "deal.propertyChange"):
            prop_name = event.get("propertyName")
            prop_value = event.get("propertyValue")

            await upsert_deal_from_properties(
                session=session,
                tenant_id=webhook_tenant_id,
                deal_id=object_id,
                stage=prop_value if prop_name == "dealstage" else None,
                amount=prop_value if prop_name == "amount" else None,
            )
            tenants_touched.add(webhook_tenant_id)
            processed += 1

    await session.commit()

    # Same audit pipeline the polling sync runs after every upsert pass (D05)
    from meridian.integrations.hubspot.audit import audit_inbound_hubspot_data

    for touched_tenant_id in tenants_touched:
        await audit_inbound_hubspot_data(session, touched_tenant_id)

    return HubSpotWebhookResponse(status="ok", processed=processed)
