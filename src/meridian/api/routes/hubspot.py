import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.api.schemas.hubspot import (
    HubspotConnectResponse,
    HubspotStatusResponse,
    HubspotWebhookResponse,
)
from meridian.api.session import get_current_tenant
from meridian.db.session import get_async_session
from meridian.integrations.hubspot.audit import audit_inbound_hubspot_data
from meridian.integrations.hubspot.client import (
    build_authorize_url,
    exchange_code_for_tokens,
    get_token_metadata,
)
from meridian.integrations.hubspot.config import get_frontend_base_url
from meridian.integrations.hubspot.credentials import (
    delete_hubspot_credentials,
    get_hubspot_credentials,
    get_tenant_by_portal_id,
    upsert_hubspot_credentials,
)
from meridian.integrations.hubspot.state import (
    InvalidOAuthStateError,
    create_oauth_state_token,
    decode_oauth_state_token,
)
from meridian.integrations.hubspot.sync import upsert_deal_from_properties
from meridian.integrations.hubspot.webhooks import verify_hubspot_v3_signature

logger = logging.getLogger(__name__)

hubspot_router = APIRouter(tags=["hubspot"])


@hubspot_router.get(
    "/integrations/hubspot/connect",
    response_model=HubspotConnectResponse,
    status_code=status.HTTP_200_OK,
)
async def hubspot_connect(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
) -> HubspotConnectResponse:
    """Generate state JWT and authorization URL for the current tenant."""
    state_token = create_oauth_state_token(tenant_id)
    authorize_url = build_authorize_url(state=state_token)
    return HubspotConnectResponse(authorize_url=authorize_url)


@hubspot_router.get("/oauth/hubspot/callback")
async def hubspot_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
) -> RedirectResponse:
    """Public OAuth callback endpoint for HubSpot."""
    frontend_url = get_frontend_base_url()

    if not state or error:
        logger.warning("HubSpot OAuth callback received error or missing state: error=%s", error)
        return RedirectResponse(f"{frontend_url}/settings/hubspot?error=oauth_failed")

    try:
        tenant_id = decode_oauth_state_token(state)
    except InvalidOAuthStateError:
        logger.warning("HubSpot OAuth callback received invalid state token")
        return RedirectResponse(f"{frontend_url}/settings/hubspot?error=invalid_state")

    if not code:
        logger.warning("HubSpot OAuth callback missing authorization code")
        return RedirectResponse(f"{frontend_url}/settings/hubspot?error=oauth_failed")

    try:
        tokens = await exchange_code_for_tokens(code)
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expires_in = tokens.get("expires_in", 21600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        metadata = await get_token_metadata(access_token)
        portal_id = str(metadata.get("hub_id", ""))
        scopes = metadata.get("scopes", [])

        await upsert_hubspot_credentials(
            session=session,
            tenant_id=tenant_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            hubspot_portal_id=portal_id if portal_id else None,
            scopes=scopes if scopes else None,
        )
    except Exception as exc:
        logger.error("Failed to complete HubSpot OAuth token exchange: %s", exc, exc_info=True)
        return RedirectResponse(f"{frontend_url}/settings/hubspot?error=oauth_failed")

    return RedirectResponse(f"{frontend_url}/settings/hubspot?connected=1")


@hubspot_router.get(
    "/integrations/hubspot/status",
    response_model=HubspotStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def hubspot_status(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: AsyncSession = Depends(get_async_session),
) -> HubspotStatusResponse:
    """Return HubSpot integration status for the current tenant."""
    creds = await get_hubspot_credentials(session, tenant_id)
    if creds is None:
        return HubspotStatusResponse(connected=False)

    return HubspotStatusResponse(
        connected=True,
        hubspot_portal_id=creds.hubspot_portal_id,
        scopes=creds.scopes,
        connected_at=creds.created_at,
        last_sync_at=creds.last_sync_at,
        last_sync_status=creds.last_sync_status,
        last_sync_error=creds.last_sync_error,
    )


@hubspot_router.delete(
    "/integrations/hubspot",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def hubspot_disconnect(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Disconnect HubSpot for the current tenant."""
    await delete_hubspot_credentials(session, tenant_id)


@hubspot_router.post(
    "/webhooks/hubspot",
    response_model=HubspotWebhookResponse,
    status_code=status.HTTP_200_OK,
)
async def hubspot_webhook(
    request: Request,
    x_hubspot_signature_v3: Annotated[str | None, Header(alias="X-HubSpot-Signature-v3")] = None,
    x_hubspot_request_timestamp: Annotated[str | None, Header(alias="X-HubSpot-Request-Timestamp")] = None,
    session: AsyncSession = Depends(get_async_session),
) -> HubspotWebhookResponse:
    """Public webhook ingestion endpoint for HubSpot."""
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")
    request_uri = str(request.url)

    # Validate v3 signature
    if not verify_hubspot_v3_signature(
        signature=x_hubspot_signature_v3,
        timestamp=x_hubspot_request_timestamp,
        method=request.method,
        uri=request_uri,
        body=body_str,
    ):
        logger.warning("Rejected HubSpot webhook: invalid signature or timestamp")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        events = await request.json()
        if not isinstance(events, list):
            events = [events]
    except Exception:
        logger.warning("Malformed JSON payload in HubSpot webhook")
        return HubspotWebhookResponse(status="ok", processed=0)

    processed = 0
    tenants_touched: set = set()
    for event in events:
        portal_id = str(event.get("portalId", ""))
        if not portal_id:
            continue

        creds = await get_tenant_by_portal_id(session, portal_id)
        if creds is None:
            logger.warning(
                "Received HubSpot webhook event for unknown portalId=%s subscriptionType=%s objectId=%s",
                portal_id,
                event.get("subscriptionType", ""),
                event.get("objectId", ""),
            )
            continue

        tenant_id = creds.tenant_id
        subscription_type = event.get("subscriptionType", "")
        object_id = str(event.get("objectId", ""))

        if subscription_type in ("deal.creation", "deal.propertyChange"):
            prop_name = event.get("propertyName")
            prop_value = event.get("propertyValue")

            await upsert_deal_from_properties(
                session=session,
                tenant_id=tenant_id,
                deal_id=object_id,
                stage=prop_value if prop_name == "dealstage" else None,
                amount=prop_value if prop_name == "amount" else None,
                entered_stage_at=(
                    datetime.now(timezone.utc) if prop_name == "dealstage" else None
                ),
            )
            tenants_touched.add(tenant_id)
            processed += 1

    await session.commit()

    # Same audit pipeline the polling sync runs after every upsert pass (D05)
    # — a webhook-created/updated deal must be audited before being trusted
    # downstream just like a polling-synced one.
    for tenant_id in tenants_touched:
        await audit_inbound_hubspot_data(session, tenant_id)

    return HubspotWebhookResponse(status="ok", processed=processed)
