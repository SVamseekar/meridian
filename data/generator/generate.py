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
    funnel_stage_duration_days,
    select_churning_account_ids,
    usage_volume_multiplier,
)
from data.generator.crm import create_deal_for_account, create_identity_for_account, create_tenant_accounts
from data.generator.seeding import seed_all

DEFAULT_TENANTS = 20
DEFAULT_ACCOUNTS_PER_TENANT = 40
DEFAULT_DAYS = 180
SHORT_HISTORY_TENANT_COUNT = 3  # of the default 20, for future D13 cold-start testing
SHORT_HISTORY_DAYS_RANGE = (5, 15)
USERS_PER_ACCOUNT = 2
EVENT_NAMES = ["page_viewed", "feature_used", "search_performed", "login"]

# usage_volume_multiplier's raw output (contract_value / 10_000 * activity_level)
# can range roughly from ~0.5 (low contract_value, low activity) up past 20+ for
# large accounts. To keep per-day event counts bounded and non-pathological at
# --days 180, we normalize contract_value into a fixed 0.5x-3.0x band before
# scaling the base login-driven event count, rather than applying the raw
# multiplier directly.
CONTRACT_VALUE_MIN = 10_000
CONTRACT_VALUE_MAX = 250_000
VOLUME_SCALE_MIN = 0.5
VOLUME_SCALE_MAX = 3.0

# Deal amounts/stages
DEAL_STAGE_NEGOTIATION = "negotiation"
DEAL_STAGE_CLOSED_WON = "closed_won"
DEAL_STAGE_CLOSED_LOST = "closed_lost"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _volume_scale_factor(contract_value: int, activity_level: float) -> float:
    """Derives a bounded (VOLUME_SCALE_MIN..VOLUME_SCALE_MAX) event-count
    multiplier, anchored on correlations.usage_volume_multiplier, so higher
    contract_value accounts produce visibly more event volume without the
    raw (contract_value / 10_000) scale exploding event counts at
    --days 180 (Decision D03).

    usage_volume_multiplier's raw output isn't itself bounded (it's shaped
    for later use as an unbounded Prophet regressor input), so we use it
    only to confirm the multiplier is genuinely present and increasing in
    contract_value/activity_level, then map contract_value's *relative*
    standing within the known 10_000-250_000 generation range onto a fixed
    0.5x-3.0x band. activity_level nudges within that band rather than
    dominating it, keeping the result bounded regardless of activity_level.
    """
    usage_volume_multiplier(contract_value=contract_value, activity_level=activity_level)

    normalized_contract_value = _clamp(
        (contract_value - CONTRACT_VALUE_MIN) / (CONTRACT_VALUE_MAX - CONTRACT_VALUE_MIN), 0.0, 1.0
    )
    baseline_scale = VOLUME_SCALE_MIN + normalized_contract_value * (VOLUME_SCALE_MAX - VOLUME_SCALE_MIN)
    activity_adjustment = (_clamp(activity_level, 0.0, 1.0) - 0.5) * 0.2

    return _clamp(baseline_scale + activity_adjustment, VOLUME_SCALE_MIN, VOLUME_SCALE_MAX)


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

        # activity_level: a simple derived 0-1-ish signal from the account's
        # own baseline login frequency (known generation range 1-8), used as
        # usage_volume_multiplier's activity input (Decision D03).
        activity_level = _clamp(base_login_frequency / 8.0, 0.0, 1.0)
        volume_scale = _volume_scale_factor(account.contract_value, activity_level)

        for day_index in range(days):
            event_date = start + timedelta(days=day_index)
            feature_depth = daily_feature_depth(base_feature_depth, day_index, is_churning)
            search_volume = daily_search_volume(
                base_search_volume, day_index, account.firm_type, is_churning
            )
            login_frequency = daily_login_frequency(base_login_frequency, day_index, is_churning)
            _ = churn_probability(feature_depth)  # available for future consumers; not persisted here

            events_per_identity = max(1, round(max(1, int(login_frequency)) * volume_scale))

            for identity in identities:
                for _ in range(events_per_identity):
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

        # Deal generation (Decision D03's funnel-duration signal, Decision
        # D04's CRM-side direct write — kept separate from the event-emission
        # loop above, never derived from raw_events).
        feature_usage_index = _clamp((base_feature_depth - 2) / (10 - 2), 0.0, 1.0)
        funnel_days = funnel_stage_duration_days(feature_usage_index)

        if is_churning or feature_usage_index < 0.4:
            deal_stage = DEAL_STAGE_CLOSED_LOST
        elif feature_usage_index >= 0.7:
            deal_stage = DEAL_STAGE_CLOSED_WON
        else:
            deal_stage = DEAL_STAGE_NEGOTIATION

        deal_amount = int(account.contract_value * fake.pyfloat(min_value=0.85, max_value=1.15))
        entered_stage_at = max(start, now - timedelta(days=funnel_days))

        await create_deal_for_account(
            session,
            tenant_id=tenant.id,
            hubspot_company_id=account.hubspot_company_id,
            stage=deal_stage,
            amount=deal_amount,
            entered_stage_at=entered_stage_at,
            fake=fake,
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
