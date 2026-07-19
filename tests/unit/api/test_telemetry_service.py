import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from meridian.api.services.telemetry import record_event
from meridian.db.base import Base
from meridian.db.models.raw_event import RawEvent


# Override UUID/JSONB type compilation for SQLite dialect, matching the shim
# pattern used in tests/unit/scripts/test_seed_dev_tenant.py.
@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # Scope to RawEvent's table only, matching the pattern in
        # tests/unit/scripts/test_seed_dev_raw_event.py — creating the full
        # Base.metadata on SQLite fails on unrelated Postgres-only column
        # types (e.g. tenant_credentials.scopes uses ARRAY).
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=[RawEvent.__table__]
            )
        )
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def test_record_event_creates_raw_event_row(db_session):
    tenant_id = uuid.uuid4()
    event = await record_event(
        db_session,
        tenant_id=tenant_id,
        anonymous_id="anon-1",
        event_name="page_viewed",
        properties={"firm_type": "boutique"},
        client_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    await db_session.commit()

    assert isinstance(event, RawEvent)
    assert event.tenant_id == tenant_id
    assert event.anonymous_id == "anon-1"
    assert event.properties == {"firm_type": "boutique"}
