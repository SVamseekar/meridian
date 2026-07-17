import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from meridian.db.models.raw_event import RawEvent


async def record_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    anonymous_id: str,
    event_name: str,
    properties: dict,
    client_timestamp: datetime,
) -> RawEvent:
    """Lands one raw telemetry event. Shared by the /telemetry/event route
    (real ingestion, rate-limited) and the generator's bulk backfill path
    (internal call, no HTTP/rate-limit overhead — see
    docs/superpowers/specs/2026-07-17-tenant-aware-generator-design.md)."""

    row = RawEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        anonymous_id=anonymous_id,
        event_name=event_name,
        properties=properties,
        client_timestamp=client_timestamp,
    )
    session.add(row)
    await session.flush()
    return row
