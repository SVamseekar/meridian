import uuid

import pytest

from scripts.hubspot_sync import main_async


@pytest.mark.asyncio
async def test_main_async_returns_zero_when_no_active_tenants(monkeypatch):
    import scripts.hubspot_sync as worker_mod

    async def mock_get_session():
        yield object()

    async def mock_list_active(session):
        return []

    monkeypatch.setattr(worker_mod, "get_async_session", mock_get_session)
    monkeypatch.setattr(worker_mod, "list_active_hubspot_tenants", mock_list_active)

    exit_code = await main_async()
    assert exit_code == 0


@pytest.mark.asyncio
async def test_main_async_returns_zero_when_all_tenants_succeed(monkeypatch):
    import scripts.hubspot_sync as worker_mod

    tenant_ids = [uuid.uuid4(), uuid.uuid4()]

    class MockCreds:
        def __init__(self, tid):
            self.tenant_id = tid

    async def mock_get_session():
        yield object()

    async def mock_list_active(session):
        return [MockCreds(t) for t in tenant_ids]

    async def mock_sync(session, tenant_id):
        return {"tenant_id": str(tenant_id), "status": "success"}

    monkeypatch.setattr(worker_mod, "get_async_session", mock_get_session)
    monkeypatch.setattr(worker_mod, "list_active_hubspot_tenants", mock_list_active)
    monkeypatch.setattr(worker_mod, "sync_tenant_inbound", mock_sync)

    exit_code = await main_async()
    assert exit_code == 0


@pytest.mark.asyncio
async def test_main_async_returns_one_when_all_tenants_fail(monkeypatch):
    import scripts.hubspot_sync as worker_mod

    tenant_ids = [uuid.uuid4()]

    class MockCreds:
        def __init__(self, tid):
            self.tenant_id = tid

    async def mock_get_session():
        yield object()

    async def mock_list_active(session):
        return [MockCreds(t) for t in tenant_ids]

    async def mock_sync(session, tenant_id):
        return {"tenant_id": str(tenant_id), "status": "failed", "error": "boom"}

    monkeypatch.setattr(worker_mod, "get_async_session", mock_get_session)
    monkeypatch.setattr(worker_mod, "list_active_hubspot_tenants", mock_list_active)
    monkeypatch.setattr(worker_mod, "sync_tenant_inbound", mock_sync)

    exit_code = await main_async()
    assert exit_code == 1


@pytest.mark.asyncio
async def test_main_async_returns_zero_on_partial_failure(monkeypatch):
    import scripts.hubspot_sync as worker_mod

    tenant_ids = [uuid.uuid4(), uuid.uuid4()]

    class MockCreds:
        def __init__(self, tid):
            self.tenant_id = tid

    async def mock_get_session():
        yield object()

    async def mock_list_active(session):
        return [MockCreds(t) for t in tenant_ids]

    call_count = {"n": 0}

    async def mock_sync(session, tenant_id):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"tenant_id": str(tenant_id), "status": "failed", "error": "boom"}
        return {"tenant_id": str(tenant_id), "status": "success"}

    monkeypatch.setattr(worker_mod, "get_async_session", mock_get_session)
    monkeypatch.setattr(worker_mod, "list_active_hubspot_tenants", mock_list_active)
    monkeypatch.setattr(worker_mod, "sync_tenant_inbound", mock_sync)

    exit_code = await main_async()
    assert exit_code == 0


@pytest.mark.asyncio
async def test_main_async_syncs_only_target_tenant_when_specified(monkeypatch):
    import scripts.hubspot_sync as worker_mod

    target_tenant_id = uuid.uuid4()
    synced_tenants = []

    async def mock_get_session():
        yield object()

    async def mock_list_active(session):
        raise AssertionError("should not be called when a target tenant is specified")

    async def mock_sync(session, tenant_id):
        synced_tenants.append(tenant_id)
        return {"tenant_id": str(tenant_id), "status": "success"}

    monkeypatch.setattr(worker_mod, "get_async_session", mock_get_session)
    monkeypatch.setattr(worker_mod, "list_active_hubspot_tenants", mock_list_active)
    monkeypatch.setattr(worker_mod, "sync_tenant_inbound", mock_sync)

    exit_code = await main_async(target_tenant_id)
    assert exit_code == 0
    assert synced_tenants == [target_tenant_id]
