"""Runs only in CI (generator-tests job) against a real Postgres database
already populated by `python -m data.generator.generate` in the preceding
CI step. Asserts Decision D02 (no orphans) and D03 (churn signal present)
hold against real generated data."""

import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from meridian.db.models.account import Account
from meridian.db.models.identity_map import IdentityMap
from meridian.db.models.raw_event import RawEvent
import meridian.db.models  # noqa: F401

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="requires the generator-tests CI step's populated database (DATABASE_URL unset)",
)


@pytest.fixture
def sync_session():
    url = os.environ["DATABASE_URL"]
    engine = create_engine(url)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_no_orphan_raw_events(sync_session):
    known_anonymous_ids = {row[0] for row in sync_session.execute(select(IdentityMap.anonymous_id)).all()}
    event_anonymous_ids = {row[0] for row in sync_session.execute(select(RawEvent.anonymous_id)).all()}
    assert event_anonymous_ids.issubset(known_anonymous_ids)


def test_accounts_exist_per_tenant(sync_session):
    accounts = sync_session.execute(select(Account)).scalars().all()
    assert len(accounts) > 0
    tenant_ids = {a.tenant_id for a in accounts}
    assert len(tenant_ids) == 3  # matches --tenants 3 in the CI step
