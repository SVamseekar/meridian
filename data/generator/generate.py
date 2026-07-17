import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from meridian.api.services.telemetry import record_event
from meridian.db.models.tenant import Tenant

from data.generator.correlations import (
    churn_probability,
    daily_feature_depth,
    daily_login_frequency,
    daily_search_volume,
    select_churning_account_ids,
)
from data.generator.crm import create_identity_for_account, create_tenant_accounts
from data.generator.seeding import seed_all

DEFAULT_TENANTS = 20
DEFAULT_ACCOUNTS_PER_TENANT = 40
DEFAULT_DAYS = 180
SHORT_HISTORY_TENANT_COUNT = 3  # of the default 20, for future D13 cold-start testing
SHORT_HISTORY_DAYS_RANGE = (5, 15)
USERS_PER_ACCOUNT = 2
EVENT_NAMES = ["page_viewed", "feature_used", "search_performed", "login"]


async def _generate_tenant(session, *, tenant_index: int, accounts_per_tenant: int, days: int, fake, seed: int):
    tenant = Tenant(id=uuid.uuid4(), name=fake.company() + " (Meridian Customer)")
    session.add(tenant)
    await session.flush()

    accounts = await create_tenant_accounts(
        session, tenant_id=tenant.id, count=accounts_per_tenant, fake=fake
    )
    account_ids = [a.id for a in accounts]
    churning_ids = select_churning_account_ids(account_ids, seed=seed + tenant_index)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    for account in accounts:
        is_churning = account.id in churning_ids
        identities = await create_identity_for_account(
            session, tenant_id=tenant.id, account_id=account.id, user_count=USERS_PER_ACCOUNT, fake=fake
        )

        base_feature_depth = fake.pyfloat(min_value=2, max_value=10)
        base_search_volume = fake.pyfloat(min_value=10, max_value=100)
        base_login_frequency = fake.pyfloat(min_value=1, max_value=8)

        for day_index in range(days):
            event_date = start + timedelta(days=day_index)
            feature_depth = daily_feature_depth(base_feature_depth, day_index, is_churning)
            search_volume = daily_search_volume(
                base_search_volume, day_index, account.firm_type, is_churning
            )
            login_frequency = daily_login_frequency(base_login_frequency, day_index, is_churning)
            _ = churn_probability(feature_depth)  # available for future consumers; not persisted here

            for identity in identities:
                for _ in range(max(1, int(login_frequency))):
                    await record_event(
                        session,
                        tenant_id=tenant.id,
                        anonymous_id=identity.anonymous_id,
                        event_name=fake.random_element(EVENT_NAMES),
                        properties={
                            "firm_type": account.firm_type,
                            "feature_depth": round(feature_depth, 2),
                            "search_volume": round(search_volume, 2),
                        },
                        client_timestamp=event_date,
                    )

    await session.commit()


async def run_generation(*, tenants: int, accounts_per_tenant: int, days: int, seed: int, session_factory) -> None:
    fake = seed_all(seed)

    short_history_indices = set(fake.random_elements(
        elements=range(tenants), length=min(SHORT_HISTORY_TENANT_COUNT, tenants), unique=True
    )) if tenants > SHORT_HISTORY_TENANT_COUNT else set()

    for tenant_index in range(tenants):
        tenant_days = (
            fake.random_int(*SHORT_HISTORY_DAYS_RANGE)
            if tenant_index in short_history_indices
            else days
        )
        async with session_factory() as session:
            await _generate_tenant(
                session,
                tenant_index=tenant_index,
                accounts_per_tenant=accounts_per_tenant,
                days=tenant_days,
                fake=fake,
                seed=seed,
            )


def main():
    parser = argparse.ArgumentParser(description="Bulk-populate synthetic Meridian tenant data.")
    parser.add_argument("--tenants", type=int, default=DEFAULT_TENANTS)
    parser.add_argument("--accounts-per-tenant", type=int, default=DEFAULT_ACCOUNTS_PER_TENANT)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()

    from meridian.db.session import get_async_sessionmaker

    session_factory = get_async_sessionmaker()
    asyncio.run(
        run_generation(
            tenants=args.tenants,
            accounts_per_tenant=args.accounts_per_tenant,
            days=args.days,
            seed=args.seed,
            session_factory=session_factory,
        )
    )
    print(f"Generated {args.tenants} tenants, {args.accounts_per_tenant} accounts each, {args.days} days.")


if __name__ == "__main__":
    main()
