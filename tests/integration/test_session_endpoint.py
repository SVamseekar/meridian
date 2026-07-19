import os
import uuid

import pytest

from meridian.db.models.tenant import Tenant


@pytest.mark.asyncio
async def test_session_issues_cookie_for_valid_tenant_and_secret(async_client, db_session, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SESSION_DEV_SECRET", "test-dev-secret")
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant")
    db_session.add(tenant)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/session",
        json={"tenant_id": str(tenant.id), "dev_secret": "test-dev-secret"},
    )

    assert response.status_code == 204
    assert "meridian_session" in response.cookies


@pytest.mark.asyncio
async def test_session_rejects_wrong_secret(async_client, db_session, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SESSION_DEV_SECRET", "test-dev-secret")
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant")
    db_session.add(tenant)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/session",
        json={"tenant_id": str(tenant.id), "dev_secret": "wrong-secret"},
    )

    assert response.status_code == 401
    assert "meridian_session" not in response.cookies


@pytest.mark.asyncio
async def test_session_rejects_unknown_tenant(async_client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SESSION_DEV_SECRET", "test-dev-secret")

    response = await async_client.post(
        "/api/v1/session",
        json={"tenant_id": str(uuid.uuid4()), "dev_secret": "test-dev-secret"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_session_returns_404_in_production_regardless_of_secret(async_client, db_session, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SESSION_DEV_SECRET", "test-dev-secret")
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant")
    db_session.add(tenant)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/session",
        json={"tenant_id": str(tenant.id), "dev_secret": "test-dev-secret"},
    )

    assert response.status_code == 404
