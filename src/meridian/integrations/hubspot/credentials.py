import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.crypto import encrypt_secret
from meridian.db.models.tenant_credentials import TenantCredentials
from meridian.integrations.hubspot.oauth import HubSpotTokenResponse

logger = logging.getLogger("meridian.hubspot")


async def upsert_hubspot_credentials(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    tokens: HubSpotTokenResponse,
    portal_id: str,
    scopes: list[str],
) -> TenantCredentials:
    existing = (
        await session.execute(
            select(TenantCredentials).where(
                TenantCredentials.tenant_id == tenant_id,
                TenantCredentials.provider == "hubspot",
            )
        )
    ).scalar_one_or_none()

    if existing is not None and set(existing.scopes or []) != set(scopes):
        logger.warning(
            '{"event": "hubspot_oauth_scope_drift_detected", "tenant_id": "%s", '
            '"previous_scopes": %s, "new_scopes": %s}',
            tenant_id,
            existing.scopes,
            scopes,
        )

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)

    if existing is not None:
        existing.hubspot_portal_id = portal_id
        existing.access_token_encrypted = encrypt_secret(tokens.access_token)
        existing.refresh_token_encrypted = encrypt_secret(tokens.refresh_token)
        existing.expires_at = expires_at
        existing.scopes = scopes
        return existing

    row = TenantCredentials(
        tenant_id=tenant_id,
        provider="hubspot",
        hubspot_portal_id=portal_id,
        access_token_encrypted=encrypt_secret(tokens.access_token),
        refresh_token_encrypted=encrypt_secret(tokens.refresh_token),
        expires_at=expires_at,
        scopes=scopes,
    )
    session.add(row)
    return row
