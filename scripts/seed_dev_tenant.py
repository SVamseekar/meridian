"""Seeds the single fixed-UUID dev tenant used by this slice's write-key
UI and API until real tenant signup/auth exists. See
docs/superpowers/specs/2026-07-17-telemetry-ingestion-slice-design.md.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from meridian.db.models.tenant import Tenant

DEV_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_TENANT_NAME = "Meridian Dev Tenant"


def seed_dev_tenant(session: Session) -> Tenant:
    existing = session.execute(
        select(Tenant).where(Tenant.id == DEV_TENANT_ID)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    tenant = Tenant(id=DEV_TENANT_ID, name=DEV_TENANT_NAME)
    session.add(tenant)
    session.flush()
    return tenant


if __name__ == "__main__":
    from meridian.db.session import get_sync_session  # created in Task 3

    with get_sync_session() as session:
        tenant = seed_dev_tenant(session)
        session.commit()
        print(f"Seeded dev tenant: {tenant.id} ({tenant.name})")
