import uuid
from datetime import datetime, timezone

import pytest
from faker import Faker
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from data.generator.crm import (
    create_deal_for_account,
    create_identity_for_account,
    create_tenant_accounts,
)
from meridian.db.base import Base
from meridian.db.models.account import Account
from meridian.db.models.identity_map import IdentityMap
from meridian.db.models.staging_hubspot_company import StagingHubspotCompany
from meridian.db.models.staging_hubspot_deal import StagingHubspotDeal


# Override UUID/ARRAY type compilation for SQLite dialect
@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(element, compiler, **kw):
    return "JSON"


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # Scope to the tables we need, avoiding Postgres-only types in other tables
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[
                    Account.__table__,
                    IdentityMap.__table__,
                    StagingHubspotCompany.__table__,
                    StagingHubspotDeal.__table__,
                ],
            )
        )
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def test_create_tenant_accounts_creates_matching_hubspot_companies(db_session):
    tenant_id = uuid.uuid4()
    fake = Faker()
    Faker.seed(1)

    accounts = await create_tenant_accounts(db_session, tenant_id=tenant_id, count=5, fake=fake)
    await db_session.commit()

    assert len(accounts) == 5
    for account in accounts:
        assert account.tenant_id == tenant_id
        assert account.hubspot_company_id is not None


async def test_create_identity_for_account_creates_requested_user_count(db_session):
    tenant_id = uuid.uuid4()
    account_id = uuid.uuid4()
    fake = Faker()
    Faker.seed(1)

    identities = await create_identity_for_account(
        db_session, tenant_id=tenant_id, account_id=account_id, user_count=3, fake=fake
    )
    await db_session.commit()

    assert len(identities) == 3
    anonymous_ids = {i.anonymous_id for i in identities}
    assert len(anonymous_ids) == 3  # all unique


async def test_create_deal_for_account_persists_expected_fields(db_session):
    tenant_id = uuid.uuid4()
    fake = Faker()
    Faker.seed(1)

    deal = await create_deal_for_account(
        db_session,
        tenant_id=tenant_id,
        hubspot_company_id="hs-co-1",
        stage="closed_won",
        amount=15000,
        entered_stage_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        fake=fake,
    )
    await db_session.commit()

    assert deal.stage == "closed_won"
    assert deal.amount == 15000
    assert deal.hubspot_company_id == "hs-co-1"
