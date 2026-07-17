"""Seeds a single deterministic raw_events row for the dev tenant so
dbt tests (relationships/not_null on stg_raw_events) have a real row
to check, both locally and in CI. See
docs/superpowers/specs/2026-07-17-dbt-staging-layer-design.md.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from meridian.db.models.raw_event import RawEvent
from scripts.seed_dev_tenant import DEV_TENANT_ID

DEV_RAW_EVENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000e1")


def seed_dev_raw_event(session: Session) -> RawEvent:
    existing = session.execute(
        select(RawEvent).where(RawEvent.id == DEV_RAW_EVENT_ID)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    event = RawEvent(
        id=DEV_RAW_EVENT_ID,
        tenant_id=DEV_TENANT_ID,
        anonymous_id="dev-seed-anon-id",
        event_name="page_viewed",
        properties={"firm_type": "boutique"},
        client_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    session.add(event)
    session.flush()
    return event


if __name__ == "__main__":
    from meridian.db.session import get_sync_session
    from scripts.seed_dev_tenant import seed_dev_tenant

    with get_sync_session() as session:
        seed_dev_tenant(session)
        event = seed_dev_raw_event(session)
        session.commit()
        print(f"Seeded dev raw_event: {event.id} (tenant={event.tenant_id})")
