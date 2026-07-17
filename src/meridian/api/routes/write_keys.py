import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.api.schemas.write_keys import WriteKeyCreated, WriteKeyMasked
from meridian.api.write_keys import generate_write_key
from meridian.db.models.tenant_write_key import TenantWriteKey
from meridian.db.session import get_async_session
from scripts.seed_dev_tenant import DEV_TENANT_ID

write_keys_router = APIRouter(prefix="/tenants/{tenant_id}/write-keys", tags=["write-keys"])


def _require_dev_tenant(tenant_id: uuid.UUID) -> None:
    # This slice has no real tenant auth (see build-sequence.md step 2 note) —
    # only the single seeded dev tenant is a valid path parameter.
    if tenant_id != DEV_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")


@write_keys_router.post("", response_model=WriteKeyCreated, status_code=201)
async def create_write_key(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> WriteKeyCreated:
    _require_dev_tenant(tenant_id)

    plaintext, key_hash = generate_write_key()
    key_id = uuid.uuid4()
    row = TenantWriteKey(id=key_id, tenant_id=tenant_id, write_key_hash=key_hash, last_four=plaintext[-4:])
    session.add(row)
    await session.commit()
    await session.refresh(row)

    return WriteKeyCreated(id=row.id, key=plaintext, created_at=row.created_at)


@write_keys_router.get("", response_model=list[WriteKeyMasked])
async def list_write_keys(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> list[WriteKeyMasked]:
    _require_dev_tenant(tenant_id)

    result = await session.execute(
        select(TenantWriteKey)
        .where(TenantWriteKey.tenant_id == tenant_id)
        .order_by(TenantWriteKey.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        WriteKeyMasked(
            id=row.id,
            masked_key=f"wk_live_{'•' * 8}{row.last_four}",
            created_at=row.created_at,
            revoked_at=row.revoked_at,
        )
        for row in rows
    ]


@write_keys_router.delete("/{key_id}", status_code=204)
async def revoke_write_key(
    tenant_id: uuid.UUID,
    key_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    _require_dev_tenant(tenant_id)

    from datetime import datetime, timezone

    result = await session.execute(
        select(TenantWriteKey).where(
            TenantWriteKey.id == key_id, TenantWriteKey.tenant_id == tenant_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Write key not found")

    row.revoked_at = datetime.now(timezone.utc)
    await session.commit()
