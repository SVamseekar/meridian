import os
from contextlib import contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker


def _sync_url() -> str:
    return os.environ["DATABASE_URL"]


def _async_url() -> str:
    # DATABASE_URL is postgresql+psycopg://... ; psycopg3 supports both
    # sync and async through the same driver name.
    return os.environ["DATABASE_URL"]


engine = create_engine(_sync_url())
SyncSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

async_engine = create_async_engine(_async_url())
AsyncSessionLocal = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
