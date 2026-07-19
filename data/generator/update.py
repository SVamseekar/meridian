import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from meridian.db.models.account import Account
from meridian.db.models.identity_map import IdentityMap

from data.generator.correlations import daily_feature_depth, daily_search_volume
from data.generator.seeding import seed_all

DEFAULT_BASE_URL = "http://localhost:8000"
EVENT_NAMES = ["page_viewed", "feature_used", "search_performed", "login"]


async def run_update_for_tenant(
    *, tenant_id, write_key_plaintext: str, days: int, seed: int, base_url: str, session_factory
) -> None:
    """Simulates N days of live SDK traffic for an existing tenant by calling
    the real POST /telemetry/event HTTP endpoint (Decision D14 write-key
    auth) — this mode's purpose is to mimic real-time ingestion, unlike
    generate.py's internal bulk write path via record_event directly.

    The plaintext write key is not recoverable from the persisted
    write_key_hash (Decision D14 — one-way hash), so callers must supply it
    explicitly (see main()'s --write-key), exactly as a real SDK integrator
    would use the plaintext key they were shown once at issuance time.
    """
    fake = seed_all(seed)

    async with session_factory() as session:
        accounts = (
            await session.execute(select(Account).where(Account.tenant_id == tenant_id))
        ).scalars().all()
        identities = (
            await session.execute(select(IdentityMap).where(IdentityMap.tenant_id == tenant_id))
        ).scalars().all()

    identities_by_account = {}
    for identity in identities:
        identities_by_account.setdefault(identity.account_id, []).append(identity)

    start = datetime.now(timezone.utc) - timedelta(days=days)

    async with httpx.AsyncClient(base_url=base_url) as client:
        for account in accounts:
            account_identities = identities_by_account.get(account.id, [])
            for day_index in range(days):
                event_date = start + timedelta(days=day_index)
                feature_depth = daily_feature_depth(base=6.0, day_index=day_index, is_churning=False)
                search_volume = daily_search_volume(
                    base=40.0, day_index=day_index, firm_type=account.firm_type, is_churning=False
                )
                for identity in account_identities:
                    response = await client.post(
                        "/telemetry/event",
                        headers={"Authorization": f"Bearer {write_key_plaintext}"},
                        json={
                            "anonymous_id": identity.anonymous_id,
                            "event_name": fake.random_element(EVENT_NAMES),
                            "properties": {
                                "firm_type": account.firm_type,
                                "feature_depth": round(feature_depth, 2),
                                "search_volume": round(search_volume, 2),
                            },
                            "client_timestamp": event_date.isoformat(),
                        },
                    )
                    if response.status_code != 202:
                        raise RuntimeError(
                            f"telemetry ingestion failed for tenant={tenant_id}: "
                            f"status={response.status_code} body={response.text}"
                        )


def main():
    parser = argparse.ArgumentParser(description="Simulate N days of live tenant traffic via the real API.")
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    parser.add_argument("--tenant-id", type=str, required=True, help="Target tenant UUID")
    parser.add_argument("--write-key", type=str, required=True, help="Plaintext write key for the target tenant")
    args = parser.parse_args()

    from meridian.db.session import get_async_sessionmaker

    session_factory = get_async_sessionmaker()
    asyncio.run(
        run_update_for_tenant(
            tenant_id=uuid.UUID(args.tenant_id),
            write_key_plaintext=args.write_key,
            days=args.days,
            seed=args.seed,
            base_url=args.base_url,
            session_factory=session_factory,
        )
    )
    print(f"Simulated {args.days} days of traffic for tenant {args.tenant_id}.")


if __name__ == "__main__":
    main()
