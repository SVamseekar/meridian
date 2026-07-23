import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from meridian.crypto import decrypt_secret
from meridian.db.models.tenant import Tenant
from meridian.db.models.tenant_credentials import TenantCredentials
from meridian.integrations.hubspot.credentials import (
    delete_hubspot_credentials,
    ensure_fresh_token,
    get_decrypted_access_token,
    get_decrypted_refresh_token,
    get_hubspot_credentials,
    get_tenant_by_portal_id,
    list_active_hubspot_tenants,
    record_hubspot_sync_result,
    upsert_hubspot_credentials,
)
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


@pytest.mark.asyncio
async def test_get_hubspot_credentials_returns_none_when_not_connected(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert await get_hubspot_credentials(db_session, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_get_tenant_by_portal_id_resolves_webhook_lookup(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="a", refresh_token="b", expires_in=1800)
    await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="99999", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    found = await get_tenant_by_portal_id(db_session, "99999")
    assert found is not None
    assert found.tenant_id == tenant_id

    assert await get_tenant_by_portal_id(db_session, "unknown-portal") is None


@pytest.mark.asyncio
async def test_list_active_hubspot_tenants_returns_connected_tenants(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="a", refresh_token="b", expires_in=1800)
    await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="123", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    active = await list_active_hubspot_tenants(db_session)
    assert any(c.tenant_id == tenant_id for c in active)


@pytest.mark.asyncio
async def test_delete_hubspot_credentials_removes_row(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="a", refresh_token="b", expires_in=1800)
    await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="123", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    deleted = await delete_hubspot_credentials(db_session, tenant_id)
    assert deleted is True
    assert await get_hubspot_credentials(db_session, tenant_id) is None
    assert await delete_hubspot_credentials(db_session, tenant_id) is False


@pytest.mark.asyncio
async def test_ensure_fresh_token_returns_existing_token_when_not_near_expiry(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="fresh-access", refresh_token="fresh-refresh", expires_in=3600)
    creds = await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="123", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    token = await ensure_fresh_token(creds, db_session)
    assert token == "fresh-access"


@pytest.mark.asyncio
async def test_ensure_fresh_token_refreshes_when_near_expiry(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("HUBSPOT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "test-client-secret")
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    # expires_in=60 puts it inside the 5-minute refresh buffer
    tokens = HubSpotTokenResponse(access_token="old-access", refresh_token="old-refresh", expires_in=60)
    creds = await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="123", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    import meridian.integrations.hubspot.credentials as credentials_mod

    async def mock_refresh(refresh_token):
        assert refresh_token == "old-refresh"
        return HubSpotTokenResponse(access_token="new-access", refresh_token="new-refresh", expires_in=21600)

    monkeypatch.setattr(
        "meridian.integrations.hubspot.oauth.refresh_access_token", mock_refresh
    )

    token = await ensure_fresh_token(creds, db_session)
    await db_session.commit()

    assert token == "new-access"
    refreshed = await get_hubspot_credentials(db_session, tenant_id)
    assert get_decrypted_access_token(refreshed) == "new-access"
    assert get_decrypted_refresh_token(refreshed) == "new-refresh"


@pytest.mark.asyncio
async def test_record_hubspot_sync_result_updates_status_fields(db_session, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    tenant_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="Test Tenant"))
    await db_session.commit()

    tokens = HubSpotTokenResponse(access_token="a", refresh_token="b", expires_in=1800)
    await upsert_hubspot_credentials(
        db_session, tenant_id, tokens, portal_id="123", scopes=["crm.objects.deals.read"]
    )
    await db_session.commit()

    await record_hubspot_sync_result(db_session, tenant_id, status="failed", error="revoked")

    creds = await get_hubspot_credentials(db_session, tenant_id)
    assert creds.last_sync_status == "failed"
    assert creds.last_sync_error == "revoked"
    assert creds.last_sync_at is not None
