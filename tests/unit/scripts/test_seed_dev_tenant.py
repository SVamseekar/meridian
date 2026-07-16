import uuid

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from meridian.db.base import Base
from meridian.db.models.tenant import Tenant
from scripts.seed_dev_tenant import DEV_TENANT_ID, seed_dev_tenant


# Override UUID type compilation for SQLite dialect
@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"


def _make_sqlite_engine(tmp_path):
    """Create a SQLite engine with PostgreSQL UUID columns mapped to strings via compilation."""
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


def test_dev_tenant_id_is_fixed():
    assert isinstance(DEV_TENANT_ID, uuid.UUID)
    # Fixed across runs/environments — re-importing must give the same value.
    from scripts.seed_dev_tenant import DEV_TENANT_ID as reimported
    assert DEV_TENANT_ID == reimported


def test_seed_dev_tenant_creates_row(tmp_path):
    engine = _make_sqlite_engine(tmp_path)
    Base.metadata.create_all(engine, tables=[Tenant.__table__])
    with Session(engine) as session:
        tenant = seed_dev_tenant(session)
        session.commit()
        assert tenant.id == DEV_TENANT_ID
        assert session.get(Tenant, DEV_TENANT_ID) is not None


def test_seed_dev_tenant_is_idempotent(tmp_path):
    engine = _make_sqlite_engine(tmp_path)
    Base.metadata.create_all(engine, tables=[Tenant.__table__])
    with Session(engine) as session:
        seed_dev_tenant(session)
        session.commit()
        seed_dev_tenant(session)  # second call must not raise or duplicate
        session.commit()
        count = session.query(Tenant).count()
        assert count == 1
