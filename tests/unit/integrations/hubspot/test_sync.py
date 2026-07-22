import uuid
from datetime import datetime, timezone
import pytest
from cryptography.fernet import Fernet

from meridian.integrations.hubspot.audit import audit_inbound_hubspot_data
from meridian.integrations.hubspot.sync import sync_tenant_inbound


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))


@pytest.mark.asyncio
async def test_sync_tenant_inbound_skipped_when_not_connected(monkeypatch):
    tenant_id = uuid.uuid4()

    import meridian.integrations.hubspot.sync as sync_mod

    async def mock_get_creds(session, tid):
        return None

    monkeypatch.setattr(sync_mod, "get_hubspot_credentials", mock_get_creds)

    res = await sync_tenant_inbound(session=None, tenant_id=tenant_id)
    assert res["status"] == "skipped_not_connected"


@pytest.mark.asyncio
async def test_sync_tenant_inbound_success_with_mock_client(monkeypatch):
    tenant_id = uuid.uuid4()

    import meridian.integrations.hubspot.sync as sync_mod

    class MockCreds:
        pass

    creds = MockCreds()
    creds.tenant_id = tenant_id

    async def mock_get_creds(session, tid):
        return creds

    async def mock_fresh_token(credentials, session):
        return "mock_access_token"

    monkeypatch.setattr(sync_mod, "get_hubspot_credentials", mock_get_creds)
    monkeypatch.setattr(sync_mod, "ensure_fresh_token", mock_fresh_token)

    class MockHubSpotClient:
        async def list_companies(self, after=None):
            return {
                "results": [
                    {"id": "101", "properties": {"name": "Acme Corp", "industry": "SaaS"}}
                ]
            }

        async def list_deals(self, after=None):
            return {
                "results": [
                    {
                        "id": "201",
                        "properties": {
                            "dealstage": "closedwon",
                            "amount": "15000",
                            "createdate": "2026-07-01T10:00:00Z",
                        },
                        "associations": {
                            "companies": {"results": [{"id": "101"}]}
                        },
                    }
                ]
            }

    class DummyScalar:
        def __init__(self, val=None):
            self._val = val

        def scalar_one_or_none(self):
            return self._val

        def scalars(self):
            return self

        def all(self):
            return []

    class DummySession:
        def __init__(self):
            self.added = []

        async def execute(self, stmt):
            return DummyScalar(None)

        def add(self, row):
            self.added.append(row)

        async def commit(self):
            pass

        async def rollback(self):
            pass

    dummy_session = DummySession()

    async def mock_audit(session, tid):
        return {"tenant_id": str(tid), "orphan_deals": 0, "missing_fields": 0}

    monkeypatch.setattr(sync_mod, "audit_inbound_hubspot_data", mock_audit)

    res = await sync_tenant_inbound(
        session=dummy_session,
        tenant_id=tenant_id,
        client=MockHubSpotClient(),
    )

    assert res["status"] == "success"
    assert res["companies_upserted"] == 1
    assert res["deals_upserted"] == 1
