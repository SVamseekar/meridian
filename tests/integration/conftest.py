import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from meridian.db.base import Base
import meridian.db.models  # noqa: F401  registers models on Base.metadata


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16") as container:
        yield container


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7") as container:
        yield container


@pytest.fixture(scope="session")
def async_engine(postgres_container):
    url = postgres_container.get_connection_url().replace("psycopg2", "psycopg")
    engine = create_async_engine(url)

    async def _create_all():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_create_all())
    yield engine


@pytest_asyncio.fixture
async def db_session(async_engine):
    async with async_engine.connect() as conn:
        trans = await conn.begin()
        session_factory = sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            yield session
        await trans.rollback()


@pytest_asyncio.fixture
async def async_client(db_session, redis_container):
    from redis.asyncio import Redis

    from meridian.api.redis_client import get_redis
    from meridian.db.session import get_async_session
    from meridian.main import app

    async def _override_get_async_session():
        yield db_session

    redis_url = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
    test_redis = Redis.from_url(redis_url)

    async def _override_get_redis():
        return test_redis

    app.dependency_overrides[get_async_session] = _override_get_async_session
    app.dependency_overrides[get_redis] = _override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await test_redis.flushdb()
