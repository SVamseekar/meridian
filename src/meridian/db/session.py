import os
from contextlib import contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker


def _database_url() -> str:
    # DATABASE_URL is postgresql+psycopg://... ; psycopg3 supports both
    # sync and async through the same driver name.
    return os.environ["DATABASE_URL"]


_sync_session_local: sessionmaker | None = None
_async_session_local: sessionmaker | None = None


def _get_sync_session_local() -> sessionmaker:
    global _sync_session_local
    if _sync_session_local is None:
        engine = create_engine(_database_url())
        _sync_session_local = sessionmaker(bind=engine, expire_on_commit=False)
    return _sync_session_local


def _get_async_session_local() -> sessionmaker:
    global _async_session_local
    if _async_session_local is None:
        async_engine = create_async_engine(_database_url())
        _async_session_local = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    return _async_session_local


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    session = _get_sync_session_local()()
    try:
        yield session
    finally:
        session.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with _get_async_session_local()() as session:
        yield session
