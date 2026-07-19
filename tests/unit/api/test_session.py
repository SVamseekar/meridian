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
