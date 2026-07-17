from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from meridian.db.base import Base
from meridian.db.models.raw_event import RawEvent
from meridian.db.models.tenant import Tenant
from scripts.seed_dev_raw_event import seed_dev_raw_event
from scripts.seed_dev_tenant import DEV_TENANT_ID, seed_dev_tenant


# Override UUID/JSONB type compilation for SQLite dialect (SQLite has no
# native UUID or JSONB types; map them to types it understands).
@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


def _make_sqlite_engine(tmp_path):
    """Create a SQLite engine with PostgreSQL UUID columns mapped to strings via compilation."""
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


def test_seed_dev_raw_event_creates_row_for_dev_tenant(tmp_path):
    engine = _make_sqlite_engine(tmp_path)
    Base.metadata.create_all(engine, tables=[Tenant.__table__, RawEvent.__table__])
    with Session(engine) as session:
        seed_dev_tenant(session)
        event = seed_dev_raw_event(session)
        session.flush()

        assert isinstance(event, RawEvent)
        assert event.tenant_id == DEV_TENANT_ID
        assert event.event_name == "page_viewed"
        assert event.properties == {"firm_type": "boutique"}


def test_seed_dev_raw_event_is_idempotent(tmp_path):
    engine = _make_sqlite_engine(tmp_path)
    Base.metadata.create_all(engine, tables=[Tenant.__table__, RawEvent.__table__])
    with Session(engine) as session:
        seed_dev_tenant(session)
        first = seed_dev_raw_event(session)
        session.flush()
        second = seed_dev_raw_event(session)
        session.flush()

        assert first.id == second.id
