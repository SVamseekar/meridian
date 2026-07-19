"""Seeds fixed-UUID dev tenants used by this slice's write-key and
HubSpot-integrations UI/API until real tenant signup/auth exists. See
docs/superpowers/specs/2026-07-17-telemetry-ingestion-slice-design.md.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from meridian.db.models.tenant import Tenant

DEV_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_TENANT_NAME = "Meridian Dev Tenant"

# Used by frontend/e2e/hubspot-integrations.spec.ts — kept distinct from
# DEV_TENANT_ID so the two e2e spec files never share tenant state.
DEV_TENANT_2_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEV_TENANT_2_NAME = "Meridian Dev Tenant 2"


def _seed_tenant(session: Session, tenant_id: uuid.UUID, name: str) -> Tenant:
    existing = session.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    tenant = Tenant(id=tenant_id, name=name)
    session.add(tenant)
    session.flush()
    return tenant


def seed_dev_tenant(session: Session) -> Tenant:
    return _seed_tenant(session, DEV_TENANT_ID, DEV_TENANT_NAME)


def seed_dev_tenant_2(session: Session) -> Tenant:
    return _seed_tenant(session, DEV_TENANT_2_ID, DEV_TENANT_2_NAME)


if __name__ == "__main__":
    from meridian.db.session import get_sync_session  # created in Task 3

    with get_sync_session() as session:
        tenant = seed_dev_tenant(session)
        tenant_2 = seed_dev_tenant_2(session)
        session.commit()
        print(f"Seeded dev tenant: {tenant.id} ({tenant.name})")
        print(f"Seeded dev tenant: {tenant_2.id} ({tenant_2.name})")
