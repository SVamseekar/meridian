import base64
import hashlib
import hmac
import time
import pytest

from meridian.integrations.hubspot.webhooks import verify_hubspot_v3_signature


def test_verify_hubspot_v3_signature_valid(monkeypatch):
    secret = "my-test-webhook-secret"
    monkeypatch.setenv("HUBSPOT_WEBHOOK_SECRET", secret)

    timestamp = str(int(time.time() * 1000))
    method = "POST"
    uri = "http://localhost:8000/api/v1/webhooks/hubspot"
    body = '[{"portalId":12345,"subscriptionType":"deal.creation"}]'

    source_string = f"{method}{uri}{body}{timestamp}"
    computed_hash = hmac.new(secret.encode("utf-8"), source_string.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.b64encode(computed_hash).decode("utf-8")

    assert verify_hubspot_v3_signature(
        signature=signature,
        timestamp=timestamp,
        method=method,
        uri=uri,
        body=body,
    ) is True


def test_verify_hubspot_v3_signature_invalid(monkeypatch):
    monkeypatch.setenv("HUBSPOT_WEBHOOK_SECRET", "my-test-webhook-secret")
    timestamp = str(int(time.time() * 1000))

    assert verify_hubspot_v3_signature(
        signature="invalid-signature",
        timestamp=timestamp,
        method="POST",
        uri="http://localhost:8000/api/v1/webhooks/hubspot",
        body="{}",
    ) is False


def test_verify_hubspot_v3_signature_expired_timestamp(monkeypatch):
    secret = "my-test-webhook-secret"
    monkeypatch.setenv("HUBSPOT_WEBHOOK_SECRET", secret)

    # 10 minutes ago
    old_timestamp = str(int((time.time() - 600) * 1000))
    method = "POST"
    uri = "http://localhost:8000/api/v1/webhooks/hubspot"
    body = "{}"

    source_string = f"{method}{uri}{body}{old_timestamp}"
    computed_hash = hmac.new(secret.encode("utf-8"), source_string.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.b64encode(computed_hash).decode("utf-8")

    assert verify_hubspot_v3_signature(
        signature=signature,
        timestamp=old_timestamp,
        method=method,
        uri=uri,
        body=body,
    ) is False
