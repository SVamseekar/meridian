import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.crypto import decrypt_secret, encrypt_secret
from meridian.db.models.tenant_credentials import TenantCredentials
from meridian.integrations.hubspot.oauth import HubSpotTokenResponse

logger = logging.getLogger("meridian.hubspot")

PROVIDER_HUBSPOT = "hubspot"


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


def get_decrypted_access_token(credentials: TenantCredentials) -> str:
    return decrypt_secret(credentials.access_token_encrypted)


def get_decrypted_refresh_token(credentials: TenantCredentials) -> str:
    return decrypt_secret(credentials.refresh_token_encrypted)


async def get_hubspot_credentials(
    session: AsyncSession, tenant_id: uuid.UUID
) -> TenantCredentials | None:
    """Retrieve HubSpot credentials for a tenant, used by the sync worker
    and status/disconnect routes."""
    result = await session.execute(
        select(TenantCredentials).where(
            TenantCredentials.tenant_id == tenant_id,
            TenantCredentials.provider == PROVIDER_HUBSPOT,
        )
    )
    return result.scalar_one_or_none()


async def get_tenant_by_portal_id(
    session: AsyncSession, portal_id: str
) -> TenantCredentials | None:
    """Resolve a HubSpot webhook's portalId back to a tenant (D09)."""
    result = await session.execute(
        select(TenantCredentials).where(
            TenantCredentials.provider == PROVIDER_HUBSPOT,
            TenantCredentials.hubspot_portal_id == str(portal_id),
        )
    )
    return result.scalar_one_or_none()


async def list_active_hubspot_tenants(session: AsyncSession) -> list[TenantCredentials]:
    """List all tenants with stored HubSpot credentials, used by the
    scheduled sync worker to iterate active connections."""
    result = await session.execute(
        select(TenantCredentials).where(TenantCredentials.provider == PROVIDER_HUBSPOT)
    )
    return list(result.scalars().all())


async def delete_hubspot_credentials(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Disconnect HubSpot for a tenant by deleting its credentials row."""
    credentials = await get_hubspot_credentials(session, tenant_id)
    if credentials is None:
        return False
    await session.delete(credentials)
    await session.commit()
    return True


async def record_hubspot_sync_result(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    status: str,
    error: str | None = None,
    commit: bool = True,
) -> None:
    """Record the durable outcome of the most recent sync/refresh attempt.

    This is the queryable staleness signal a status endpoint reads — a
    credentials row existing only means a tenant once connected; this is
    what tells you whether the connection is still actually working.
    `commit=False` lets a caller folding this into a larger unit of work
    (e.g. the sync worker's own transaction) defer the commit."""
    credentials = await get_hubspot_credentials(session, tenant_id)
    if credentials is None:
        return

    credentials.last_sync_at = datetime.now(timezone.utc)
    credentials.last_sync_status = status
    credentials.last_sync_error = error

    if commit:
        await session.commit()
    else:
        await session.flush()


async def ensure_fresh_token(
    credentials: TenantCredentials,
    session: AsyncSession,
) -> str:
    """Return a valid access token for `credentials`, proactively refreshing
    it first if it's within 5 minutes of expiry (D09). The refreshed
    credentials are flushed (not committed) so the caller's own transaction
    covers them — a later failure in that same unit of work rolls the
    refresh back too, instead of leaving it durably persisted while the
    rest of the work fails."""
    from meridian.integrations.hubspot.oauth import refresh_access_token

    now = datetime.now(timezone.utc)
    expires_at = credentials.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at - now > timedelta(minutes=5):
        return get_decrypted_access_token(credentials)

    logger.info(
        '{"event": "hubspot_token_refresh_started", "tenant_id": "%s"}', credentials.tenant_id
    )
    refresh_token = get_decrypted_refresh_token(credentials)
    tokens = await refresh_access_token(refresh_token)

    credentials.access_token_encrypted = encrypt_secret(tokens.access_token)
    credentials.refresh_token_encrypted = encrypt_secret(tokens.refresh_token)
    credentials.expires_at = now + timedelta(seconds=tokens.expires_in)
    await session.flush()

    return tokens.access_token
