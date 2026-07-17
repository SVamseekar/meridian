import pytest

from meridian.db.session import get_sync_session, get_async_session


def test_get_sync_session_is_context_manager():
    cm = get_sync_session()
    assert hasattr(cm, "__enter__") and hasattr(cm, "__exit__")


def test_get_async_session_is_async_generator_function():
    import inspect
    assert inspect.isasyncgenfunction(get_async_session)
