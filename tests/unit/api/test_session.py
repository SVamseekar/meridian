import time
import uuid

import pytest
from jose import jwt

from meridian.api.session import (
    InvalidSessionTokenError,
    create_session_token,
    decode_session_token,
)


def test_create_session_token_round_trips_tenant_id():
    tenant_id = uuid.uuid4()
    token = create_session_token(tenant_id)
    assert decode_session_token(token) == tenant_id


def test_decode_session_token_rejects_tampered_signature():
    tenant_id = uuid.uuid4()
    token = create_session_token(tenant_id)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(InvalidSessionTokenError):
        decode_session_token(tampered)


def test_decode_session_token_rejects_expired_token(monkeypatch):
    import meridian.api.session as session_module

    monkeypatch.setattr(session_module, "SESSION_TOKEN_TTL_SECONDS", -1)
    tenant_id = uuid.uuid4()
    token = create_session_token(tenant_id)
    with pytest.raises(InvalidSessionTokenError):
        decode_session_token(token)


def test_decode_session_token_rejects_malformed_token():
    with pytest.raises(InvalidSessionTokenError):
        decode_session_token("not-a-jwt")


def test_create_session_token_sets_expiry_one_hour_out(monkeypatch):
    tenant_id = uuid.uuid4()
    before = int(time.time())
    token = create_session_token(tenant_id)
    claims = jwt.get_unverified_claims(token)
    assert claims["exp"] - before in range(3595, 3606)  # ~1 hour, small tolerance


from fastapi import HTTPException, Request

from meridian.api.session import get_current_tenant


def _fake_request(cookie_value: str | None) -> Request:
    cookies = {} if cookie_value is None else {"meridian_session": cookie_value}
    scope = {
        "type": "http",
        "headers": [
            (b"cookie", f"meridian_session={cookie_value}".encode())
        ] if cookie_value is not None else [],
    }
    request = Request(scope)
    request._cookies = cookies
    return request


@pytest.mark.asyncio
async def test_get_current_tenant_returns_tenant_id_for_valid_cookie():
    tenant_id = uuid.uuid4()
    token = create_session_token(tenant_id)
    request = _fake_request(token)

    result = await get_current_tenant(request)

    assert result == tenant_id


@pytest.mark.asyncio
async def test_get_current_tenant_raises_401_for_missing_cookie():
    request = _fake_request(None)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_tenant(request)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_tenant_raises_401_for_invalid_cookie():
    request = _fake_request("garbage-token")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_tenant(request)

    assert exc_info.value.status_code == 401
