"""Scheduled HubSpot inbound sync worker (D10). Iterates all tenants with a
stored HubSpot connection and runs a polling sync pass for each, isolating
one tenant's failure from the rest of the batch (domain-rules.md §5)."""

import argparse
import asyncio
import logging
import sys
import uuid

from meridian.db.session import get_async_session
from meridian.integrations.hubspot.credentials import list_active_hubspot_tenants
from meridian.integrations.hubspot.sync import sync_tenant_inbound
from meridian.logging_config import configure_logging

logger = logging.getLogger("meridian.scripts.hubspot_sync")


async def main_async(target_tenant_id: uuid.UUID | None = None) -> int:
    configure_logging()
    logger.info('{"event": "hubspot_sync_worker_started"}')

    async for session in get_async_session():
        if target_tenant_id:
            tenants_to_sync = [target_tenant_id]
        else:
            active_creds = await list_active_hubspot_tenants(session)
            tenants_to_sync = [creds.tenant_id for creds in active_creds]

        if not tenants_to_sync:
            logger.info('{"event": "hubspot_sync_worker_no_active_tenants"}')
            return 0

        logger.info('{"event": "hubspot_sync_worker_tenant_count", "count": %d}', len(tenants_to_sync))
        failures = 0
        for tenant_id in tenants_to_sync:
            res = await sync_tenant_inbound(session, tenant_id)
            if res.get("status") == "failed":
                failures += 1

        if failures > 0:
            logger.warning(
                '{"event": "hubspot_sync_worker_partial_failure", "failures": %d, "total": %d}',
                failures,
                len(tenants_to_sync),
            )
            if failures == len(tenants_to_sync):
                return 1

        logger.info('{"event": "hubspot_sync_worker_completed"}')
        return 0

    return 0


def main():
    parser = argparse.ArgumentParser(description="Meridian HubSpot Inbound Sync Worker")
    parser.add_argument("--tenant-id", type=str, help="Optional tenant UUID to sync specifically")
    args = parser.parse_args()

    tenant_uuid = uuid.UUID(args.tenant_id) if args.tenant_id else None
    exit_code = asyncio.run(main_async(tenant_uuid))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
