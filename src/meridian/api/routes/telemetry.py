import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.api.rate_limit import RateLimiter
from meridian.api.redis_client import get_redis
from meridian.api.schemas.telemetry import TelemetryEventAck, TelemetryEventIn
from meridian.api.write_keys import hash_write_key
from meridian.db.models.raw_event import RawEvent
from meridian.db.models.tenant_write_key import TenantWriteKey
from meridian.db.session import get_async_session

logger = logging.getLogger("meridian.telemetry")

telemetry_router = APIRouter(prefix="/telemetry", tags=["telemetry"])

TELEMETRY_RATE_LIMIT = 100  # requests/sec/tenant, see Decision D14/D15
TELEMETRY_RATE_WINDOW_SECONDS = 1


async def _resolve_tenant_id(
    authorization: str | None,
    session: AsyncSession,
) -> "uuid.UUID":
    import uuid

    if not authorization or not authorization.startswith("Bearer "):
        logger.warning(
            "telemetry auth rejected: missing or malformed Authorization header (route=/telemetry/event)"
        )
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    plaintext = authorization.removeprefix("Bearer ").strip()
    key_hash = hash_write_key(plaintext)

    result = await session.execute(
        select(TenantWriteKey).where(
            TenantWriteKey.write_key_hash == key_hash,
            TenantWriteKey.revoked_at.is_(None),
        )
    )
    write_key = result.scalar_one_or_none()
    if write_key is None:
        logger.warning(
            "telemetry auth rejected: invalid or revoked write key (route=/telemetry/event)"
        )
        raise HTTPException(status_code=401, detail="Invalid or revoked write key")

    return write_key.tenant_id


@telemetry_router.post("/event", response_model=TelemetryEventAck, status_code=202)
async def ingest_event(
    event: TelemetryEventIn,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_async_session),
    redis=Depends(get_redis),
) -> TelemetryEventAck:
    tenant_id = await _resolve_tenant_id(authorization, session)
    request.state.tenant_id = str(tenant_id)

    limiter = RateLimiter(redis)
    allowed = await limiter.check_and_increment(
        key=f"telemetry:{tenant_id}",
        limit=TELEMETRY_RATE_LIMIT,
        window_seconds=TELEMETRY_RATE_WINDOW_SECONDS,
    )
    if not allowed:
        logger.warning(
            "telemetry rate limit exceeded (route=/telemetry/event, tenant_id=%s)",
            tenant_id,
        )
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    import uuid

    row = RawEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        anonymous_id=event.anonymous_id,
        event_name=event.event_name,
        properties=event.properties,
        client_timestamp=event.client_timestamp,
    )
    session.add(row)
    await session.commit()

    return TelemetryEventAck()
