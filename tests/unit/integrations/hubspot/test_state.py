import time
import uuid

import pytest
from jose import jwt

from meridian.integrations.hubspot.state import (
    InvalidOAuthStateError,
    create_oauth_state_token,
    decode_oauth_state_token,
)


def test_create_oauth_state_token_round_trips_tenant_id(monkeypatch):
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-state-secret")
    tenant_id = uuid.uuid4()

    token = create_oauth_state_token(tenant_id)

    assert decode_oauth_state_token(token) == tenant_id


def test_decode_oauth_state_token_rejects_tampered_signature(monkeypatch):
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-state-secret")
    token = create_oauth_state_token(uuid.uuid4())
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    with pytest.raises(InvalidOAuthStateError):
        decode_oauth_state_token(tampered)


def test_decode_oauth_state_token_rejects_expired_token(monkeypatch):
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-state-secret")
    import meridian.integrations.hubspot.state as state_module

    monkeypatch.setattr(state_module, "OAUTH_STATE_TTL_SECONDS", -1)
    token = create_oauth_state_token(uuid.uuid4())

    with pytest.raises(InvalidOAuthStateError):
        decode_oauth_state_token(token)


def test_decode_oauth_state_token_rejects_malformed_token(monkeypatch):
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-state-secret")

    with pytest.raises(InvalidOAuthStateError):
        decode_oauth_state_token("not-a-jwt")


def test_create_oauth_state_token_includes_a_nonce(monkeypatch):
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-state-secret")
    tenant_id = uuid.uuid4()

    token_a = create_oauth_state_token(tenant_id)
    token_b = create_oauth_state_token(tenant_id)

    claims_a = jwt.get_unverified_claims(token_a)
    claims_b = jwt.get_unverified_claims(token_b)
    assert claims_a["nonce"] != claims_b["nonce"]


def test_create_oauth_state_token_sets_ten_minute_expiry(monkeypatch):
    monkeypatch.setenv("HUBSPOT_OAUTH_STATE_SECRET", "test-state-secret")
    before = int(time.time())

    token = create_oauth_state_token(uuid.uuid4())

    claims = jwt.get_unverified_claims(token)
    assert claims["exp"] - before in range(595, 606)
