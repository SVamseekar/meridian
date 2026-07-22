import uuid
from datetime import datetime, timedelta, timezone
import pytest
from cryptography.fernet import Fernet

from meridian.integrations.hubspot.credentials import (
    delete_hubspot_credentials,
    get_decrypted_access_token,
    get_decrypted_refresh_token,
    get_hubspot_credentials,
    get_tenant_by_portal_id,
    list_active_hubspot_tenants,
    upsert_hubspot_credentials,
)


@pytest.fixture(autouse=True)
def setup_encryption_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))


@pytest.mark.asyncio
async def test_upsert_and_retrieve_hubspot_credentials(db_session):
    tenant_id = uuid.uuid4()
    access_token = "access_token_abc123"
    refresh_token = "refresh_token_xyz789"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    portal_id = "portal_12345"
    scopes = ["crm.objects.contacts.read", "companies.read"]

    creds = await upsert_hubspot_credentials(
        session=db_session,
        tenant_id=tenant_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        hubspot_portal_id=portal_id,
        scopes=scopes,
    )

    assert creds.tenant_id == tenant_id
    assert creds.provider == "hubspot"
    assert creds.hubspot_portal_id == portal_id
    assert creds.scopes == scopes
    assert get_decrypted_access_token(creds) == access_token
    assert get_decrypted_refresh_token(creds) == refresh_token

    # Retrieve by tenant_id
    retrieved = await get_hubspot_credentials(db_session, tenant_id)
    assert retrieved is not None
    assert retrieved.tenant_id == tenant_id
    assert get_decrypted_access_token(retrieved) == access_token

    # Lookup by portal_id
    by_portal = await get_tenant_by_portal_id(db_session, portal_id)
    assert by_portal is not None
    assert by_portal.tenant_id == tenant_id

    # List active tenants
    active = await list_active_hubspot_tenants(db_session)
    assert any(c.tenant_id == tenant_id for c in active)

    # Upsert to update tokens
    new_access = "new_access_token_999"
    updated = await upsert_hubspot_credentials(
        session=db_session,
        tenant_id=tenant_id,
        access_token=new_access,
        refresh_token=refresh_token,
        expires_at=expires_at,
        hubspot_portal_id=portal_id,
        scopes=scopes,
    )
    assert get_decrypted_access_token(updated) == new_access

    # Delete credentials
    deleted = await delete_hubspot_credentials(db_session, tenant_id)
    assert deleted is True
    assert await get_hubspot_credentials(db_session, tenant_id) is None
