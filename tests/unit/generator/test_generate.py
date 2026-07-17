import pytest
from sqlalchemy import ARRAY, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from data.generator.generate import run_generation
from meridian.db.base import Base
from meridian.db.models.account import Account
from meridian.db.models.identity_map import IdentityMap
from meridian.db.models.raw_event import RawEvent
from meridian.db.models.staging_hubspot_deal import StagingHubspotDeal
from meridian.db.models.tenant import Tenant
import meridian.db.models  # noqa: F401


# Override UUID/ARRAY/JSONB type compilation for SQLite dialect, matching the
# shim pattern used in tests/unit/scripts/test_seed_dev_tenant.py and
# tests/unit/generator/test_crm.py — needed here because run_generation
# exercises the full Base.metadata (including tenant_credentials.scopes
# ARRAY and raw_events.properties JSONB, both Postgres-only types).
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
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine


async def test_run_generation_creates_expected_tenant_and_account_counts(engine):
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    await run_generation(
        tenants=2, accounts_per_tenant=3, days=10, seed=42, session_factory=session_factory
    )

    async with session_factory() as session:
        tenants = (await session.execute(select(Tenant))).scalars().all()
        accounts = (await session.execute(select(Account))).scalars().all()
        assert len(tenants) == 2
        assert len(accounts) == 6  # 2 tenants * 3 accounts each


async def test_run_generation_creates_raw_events_resolvable_via_identity_map(engine):
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    await run_generation(
        tenants=1, accounts_per_tenant=2, days=5, seed=42, session_factory=session_factory
    )

    async with session_factory() as session:
        events = (await session.execute(select(RawEvent))).scalars().all()
        identities = (await session.execute(select(IdentityMap))).scalars().all()
        assert len(events) > 0

        known_anonymous_ids = {i.anonymous_id for i in identities}
        for event in events:
            assert event.anonymous_id in known_anonymous_ids  # no orphan events, Decision D02


async def test_run_generation_is_deterministic_for_same_seed(engine):
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    await run_generation(
        tenants=1, accounts_per_tenant=2, days=5, seed=42, session_factory=session_factory
    )

    async with session_factory() as session:
        first_run_accounts = sorted(
            a.name for a in (await session.execute(select(Account))).scalars().all()
        )

    # Second engine/run with the same seed
    engine2 = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine2.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory2 = sessionmaker(bind=engine2, class_=AsyncSession, expire_on_commit=False)

    await run_generation(
        tenants=1, accounts_per_tenant=2, days=5, seed=42, session_factory=session_factory2
    )

    async with session_factory2() as session:
        second_run_accounts = sorted(
            a.name for a in (await session.execute(select(Account))).scalars().all()
        )

    assert first_run_accounts == second_run_accounts


async def test_run_generation_creates_one_deal_per_account(engine):
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    await run_generation(
        tenants=1, accounts_per_tenant=4, days=5, seed=42, session_factory=session_factory
    )

    async with session_factory() as session:
        accounts = (await session.execute(select(Account))).scalars().all()
        deals = (await session.execute(select(StagingHubspotDeal))).scalars().all()

        assert len(deals) == len(accounts)
        assert len(deals) > 0

        account_company_ids = {a.hubspot_company_id for a in accounts}
        for deal in deals:
            assert deal.hubspot_company_id in account_company_ids
            assert deal.amount > 0
            assert deal.stage in {"negotiation", "closed_won", "closed_lost"}


async def test_run_generation_scales_event_volume_with_contract_value(engine):
    # With a fixed seed, contract_value is randomized per account but
    # deterministic across runs. We generate a modest cohort and confirm the
    # highest-contract-value account produced at least as many events as the
    # lowest-contract-value account, and strictly more in the common case —
    # i.e. usage_volume_multiplier is genuinely influencing event counts.
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    await run_generation(
        tenants=1, accounts_per_tenant=10, days=10, seed=42, session_factory=session_factory
    )

    async with session_factory() as session:
        accounts = (await session.execute(select(Account))).scalars().all()
        identities = (await session.execute(select(IdentityMap))).scalars().all()
        events = (await session.execute(select(RawEvent))).scalars().all()

        identity_to_account = {i.anonymous_id: i.account_id for i in identities}
        events_per_account = {}
        for event in events:
            account_id = identity_to_account[event.anonymous_id]
            events_per_account[account_id] = events_per_account.get(account_id, 0) + 1

        accounts_sorted = sorted(accounts, key=lambda a: a.contract_value)
        lowest = accounts_sorted[0]
        highest = accounts_sorted[-1]

        assert events_per_account.get(highest.id, 0) >= events_per_account.get(lowest.id, 0)
        assert events_per_account.get(highest.id, 0) > events_per_account.get(lowest.id, 0)
