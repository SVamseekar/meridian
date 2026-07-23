import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from meridian.db.models.staging_hubspot_deal import StagingHubspotDeal
from meridian.db.models.tenant import Tenant
from meridian.integrations.hubspot.credentials import upsert_hubspot_credentials
from meridian.integrations.hubspot.oauth import HubSpotTokenResponse


def _sign(secret: str, method: str, uri: str, body: str, timestamp: str) -> str:
    source_string = f"{method}{uri}{body}{timestamp}"
    computed_hash = hmac.new(secret.encode("utf-8"), source_string.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(computed_hash).decode("utf-8")


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    monkeypatch.setenv("HUBSPOT_WEBHOOK_SECRET", "test-webhook-secret")


@pytest.mark.asyncio
async def test_webhook_deal_creation_upserts_and_audits(async_client, db_session):
    tenant_id = uuid.uuid4()
    portal_id = "555"
    db_session.add(Tenant(id=tenant_id, name="Webhook Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="a", refresh_token="b", expires_in=1800)
    await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id=portal_id, scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    body_obj = [
        {
            "portalId": 555,
            "subscriptionType": "deal.creation",
            "objectId": 9001,
            "propertyName": "dealstage",
            "propertyValue": "closedwon",
        }
    ]
    body = json.dumps(body_obj)
    method = "POST"
    uri = "http://test/api/v1/webhooks/hubspot"
    timestamp = str(int(time.time() * 1000))
    signature = _sign("test-webhook-secret", method, uri, body, timestamp)

    response = await async_client.post(
        "/api/v1/webhooks/hubspot",
        content=body,
        headers={
            "X-HubSpot-Signature-v3": signature,
            "X-HubSpot-Request-Timestamp": timestamp,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "processed": 1}

    result = await db_session.execute(
        select(StagingHubspotDeal).where(
            StagingHubspotDeal.tenant_id == tenant_id,
            StagingHubspotDeal.hubspot_deal_id == "9001",
        )
    )
    deal = result.scalar_one_or_none()
    assert deal is not None
    assert deal.stage == "closedwon"
    assert deal.hubspot_company_id == "orphan"


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(async_client):
    response = await async_client.post(
        "/api/v1/webhooks/hubspot",
        content="[]",
        headers={
            "X-HubSpot-Signature-v3": "bogus",
            "X-HubSpot-Request-Timestamp": str(int(time.time() * 1000)),
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_unknown_portal_id_is_ignored_not_rejected(async_client):
    body = json.dumps([{"portalId": 999999, "subscriptionType": "deal.creation", "objectId": 1}])
    method = "POST"
    uri = "http://test/api/v1/webhooks/hubspot"
    timestamp = str(int(time.time() * 1000))
    signature = _sign("test-webhook-secret", method, uri, body, timestamp)

    response = await async_client.post(
        "/api/v1/webhooks/hubspot",
        content=body,
        headers={
            "X-HubSpot-Signature-v3": signature,
            "X-HubSpot-Request-Timestamp": timestamp,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "processed": 0}
