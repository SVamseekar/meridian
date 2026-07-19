import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from data.generator.update import run_update_for_tenant
from meridian.db.base import Base
from meridian.db.models.account import Account
from meridian.db.models.identity_map import IdentityMap
from meridian.db.models.tenant import Tenant
from meridian.db.models.tenant_write_key import TenantWriteKey
import meridian.db.models  # noqa: F401
from meridian.api.write_keys import generate_write_key


# Override UUID/ARRAY/JSONB type compilation for SQLite dialect, matching the
# shim pattern used in tests/unit/generator/test_generate.py — needed here
# because Base.metadata.create_all touches the full schema (including
# Postgres-only types elsewhere in the metadata), even though this test's
# own fixtures only use tenants/tenant_write_keys/accounts/identity_map.
@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(element, compiler, **kw):
    return "JSON"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


@pytest.fixture
async def seeded_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        tenant = Tenant(id=uuid.uuid4(), name="Test Tenant")
        session.add(tenant)

        plaintext, key_hash = generate_write_key()
        session.add(TenantWriteKey(id=uuid.uuid4(), tenant_id=tenant.id, write_key_hash=key_hash, last_four=plaintext[-4:]))

        account = Account(
            id=uuid.uuid4(), tenant_id=tenant.id, hubspot_company_id="hs-co-1",
            name="Acme", firm_type="boutique", contract_value=50000,
        )
        session.add(account)
        await session.flush()

        identity = IdentityMap(
            id=uuid.uuid4(), tenant_id=tenant.id, anonymous_id="anon-1",
            user_id=uuid.uuid4(), account_id=account.id,
        )
        session.add(identity)
        await session.commit()

    yield session_factory, tenant.id, plaintext


async def test_run_update_posts_events_via_http_for_each_active_tenant(seeded_engine):
    session_factory, tenant_id, plaintext = seeded_engine

    mock_response = AsyncMock()
    mock_response.status_code = 202

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        await run_update_for_tenant(
            tenant_id=tenant_id,
            write_key_plaintext=plaintext,
            days=2,
            seed=42,
            base_url="http://test",
            session_factory=session_factory,
        )

    assert mock_post.called
    call_args = mock_post.call_args
    assert call_args.args[0] == "/telemetry/event" or "/telemetry/event" in str(call_args)
    headers = call_args.kwargs.get("headers", {})
    assert "Authorization" in headers
    assert headers["Authorization"] == f"Bearer {plaintext}"


async def test_run_update_spreads_event_timestamps_across_simulated_days(seeded_engine):
    session_factory, tenant_id, plaintext = seeded_engine

    mock_response = AsyncMock()
    mock_response.status_code = 202

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        await run_update_for_tenant(
            tenant_id=tenant_id,
            write_key_plaintext=plaintext,
            days=3,
            seed=42,
            base_url="http://test",
            session_factory=session_factory,
        )

    client_timestamps = [
        call.kwargs["json"]["client_timestamp"] for call in mock_post.call_args_list
    ]
    assert len(client_timestamps) > 0

    # Timestamps must vary across the simulated days, not all collapse to
    # "now" — otherwise the --days N temporal spread is lost.
    distinct_timestamps = set(client_timestamps)
    assert len(distinct_timestamps) >= 3

    parsed_dates = sorted({ts[:10] for ts in client_timestamps})
    assert len(parsed_dates) == 3
