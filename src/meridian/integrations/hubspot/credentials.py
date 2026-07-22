import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.db.models.tenant_credentials import TenantCredentials
from meridian.security.encryption import decrypt_token, encrypt_token

PROVIDER_HUBSPOT = "hubspot"


def get_decrypted_access_token(credentials: TenantCredentials) -> str:
    """Decrypt access_token_encrypted from a TenantCredentials record."""
    return decrypt_token(credentials.access_token_encrypted)


def get_decrypted_refresh_token(credentials: TenantCredentials) -> str:
    """Decrypt refresh_token_encrypted from a TenantCredentials record."""
    return decrypt_token(credentials.refresh_token_encrypted)


async def upsert_hubspot_credentials(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    hubspot_portal_id: str | None = None,
    scopes: list[str] | None = None,
    commit: bool = True,
) -> TenantCredentials:
    """Upsert encrypted HubSpot credentials for a tenant.

    `commit=False` lets a caller that owns a larger unit of work (e.g. a sync
    pass that upserts CRM rows after refreshing the token) fold this write
    into its own transaction instead of committing it immediately — so a
    later failure in that unit of work rolls back the credential update too,
    rather than leaving it durably persisted while the rest of the pass fails.
    """
    # Ensure expires_at is timezone-aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    encrypted_access = encrypt_token(access_token)
    encrypted_refresh = encrypt_token(refresh_token)

    result = await session.execute(
        select(TenantCredentials).where(
            TenantCredentials.tenant_id == tenant_id,
            TenantCredentials.provider == PROVIDER_HUBSPOT,
        )
    )
    credentials = result.scalar_one_or_none()

    if credentials is None:
        credentials = TenantCredentials(
            tenant_id=tenant_id,
            provider=PROVIDER_HUBSPOT,
            hubspot_portal_id=hubspot_portal_id,
            access_token_encrypted=encrypted_access,
            refresh_token_encrypted=encrypted_refresh,
            expires_at=expires_at,
            scopes=scopes,
        )
        session.add(credentials)
    else:
        credentials.access_token_encrypted = encrypted_access
        credentials.refresh_token_encrypted = encrypted_refresh
        credentials.expires_at = expires_at
        if hubspot_portal_id is not None:
            credentials.hubspot_portal_id = hubspot_portal_id
        if scopes is not None:
            credentials.scopes = scopes

    if commit:
        await session.commit()
        await session.refresh(credentials)
    else:
        await session.flush()
    return credentials


async def get_hubspot_credentials(
    session: AsyncSession, tenant_id: uuid.UUID
) -> TenantCredentials | None:
    """Retrieve HubSpot credentials for a tenant."""
    result = await session.execute(
        select(TenantCredentials).where(
            TenantCredentials.tenant_id == tenant_id,
            TenantCredentials.provider == PROVIDER_HUBSPOT,
        )
    )
    return result.scalar_one_or_none()


async def delete_hubspot_credentials(
    session: AsyncSession, tenant_id: uuid.UUID
) -> bool:
    """Delete (disconnect) HubSpot credentials for a tenant."""
    credentials = await get_hubspot_credentials(session, tenant_id)
    if credentials is None:
        return False
    await session.delete(credentials)
    await session.commit()
    return True


async def list_active_hubspot_tenants(
    session: AsyncSession,
) -> list[TenantCredentials]:
    """List all tenant credential records for HubSpot."""
    result = await session.execute(
        select(TenantCredentials).where(
            TenantCredentials.provider == PROVIDER_HUBSPOT
        )
    )
    return list(result.scalars().all())


async def get_tenant_by_portal_id(
    session: AsyncSession, portal_id: str
) -> TenantCredentials | None:
    """Retrieve HubSpot credentials by portal_id (used for webhook resolution)."""
    result = await session.execute(
        select(TenantCredentials).where(
            TenantCredentials.provider == PROVIDER_HUBSPOT,
            TenantCredentials.hubspot_portal_id == str(portal_id),
        )
    )
    return result.scalar_one_or_none()


async def record_hubspot_sync_result(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    status: str,
    error: str | None = None,
    commit: bool = True,
) -> None:
    """Record the durable outcome of the most recent sync/refresh attempt.

    This is the queryable staleness signal `hubspot_status` reads — a
    credentials row existing only means a tenant once connected; this is
    what tells you whether the connection is still actually working."""
    result = await session.execute(
        select(TenantCredentials).where(
            TenantCredentials.tenant_id == tenant_id,
            TenantCredentials.provider == PROVIDER_HUBSPOT,
        )
    )
    credentials = result.scalar_one_or_none()
    if credentials is None:
        return

    credentials.last_sync_at = datetime.now(timezone.utc)
    credentials.last_sync_status = status
    credentials.last_sync_error = error

    if commit:
        await session.commit()
    else:
        await session.flush()
