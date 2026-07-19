import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from meridian.crypto import decrypt_secret
from meridian.db.models.tenant import Tenant
from meridian.db.models.tenant_credentials import TenantCredentials
from meridian.integrations.hubspot.credentials import upsert_hubspot_credentials
from meridian.integrations.hubspot.oauth import HubSpotTokenResponse


@pytest.mark.asyncio
async def test_upsert_creates_new_row_with_encrypted_tokens(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="hs-access", refresh_token="hs-refresh", expires_in=1800)

    before = datetime.now(timezone.utc)
    row = await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="12345", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    assert row.tenant_id == tenant_id
    assert row.provider == "hubspot"
    assert row.hubspot_portal_id == "12345"
    assert row.access_token_encrypted != b"hs-access"
    assert decrypt_secret(row.access_token_encrypted) == "hs-access"
    assert decrypt_secret(row.refresh_token_encrypted) == "hs-refresh"
    assert row.expires_at > before + timedelta(seconds=1700)
    assert row.scopes == ["crm.objects.deals.read"]


@pytest.mark.asyncio
async def test_upsert_overwrites_existing_row_on_reconnect(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    first_tokens = HubSpotTokenResponse(access_token="first-access", refresh_token="first-refresh", expires_in=1800)
    await upsert_hubspot_credentials(
        db_session, tenant_id, first_tokens, portal_id="12345", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    second_tokens = HubSpotTokenResponse(access_token="second-access", refresh_token="second-refresh", expires_in=1800)
    await upsert_hubspot_credentials(
        db_session, tenant_id, second_tokens, portal_id="12345", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    result = await db_session.execute(
        select(TenantCredentials).where(
            TenantCredentials.tenant_id == tenant_id, TenantCredentials.provider == "hubspot"
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert decrypt_secret(rows[0].access_token_encrypted) == "second-access"


@pytest.mark.asyncio
async def test_upsert_logs_scope_drift_on_reconnect_with_different_scopes(db_session, monkeypatch, caplog):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="a", refresh_token="b", expires_in=1800)
    await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="12345", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    with caplog.at_level("WARNING", logger="meridian.hubspot"):
        await upsert_hubspot_credentials(
            db_session,
            tenant_id,
            tokens,
            portal_id="12345",
            scopes=["crm.objects.deals.read", "crm.objects.companies.write"],
        )
        await db_session.commit()

    assert any("hubspot_oauth_scope_drift_detected" in record.message for record in caplog.records)
