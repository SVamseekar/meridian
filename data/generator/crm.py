import uuid
from datetime import datetime

from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.db.models.account import Account
from meridian.db.models.identity_map import IdentityMap
from meridian.db.models.staging_hubspot_company import StagingHubspotCompany
from meridian.db.models.staging_hubspot_deal import StagingHubspotDeal

FIRM_TYPES = ["boutique", "midmarket", "enterprise"]


async def create_tenant_accounts(
    session: AsyncSession, *, tenant_id: uuid.UUID, count: int, fake: Faker
) -> list[Account]:
    """Creates `count` end-customer accounts for a tenant, each with a
    matching staging_hubspot_companies row (Decision D04 — CRM-side data
    is a separate table, joined only through identity_map elsewhere, never
    back-filled from raw_events)."""

    accounts = []
    for _ in range(count):
        hubspot_company_id = f"hs-co-{uuid.uuid4().hex[:12]}"
        company_name = fake.company()
        firm_type = fake.random_element(FIRM_TYPES)

        session.add(
            StagingHubspotCompany(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                hubspot_company_id=hubspot_company_id,
                name=company_name,
                firm_type=firm_type,
            )
        )

        account = Account(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            hubspot_company_id=hubspot_company_id,
            name=company_name,
            firm_type=firm_type,
            contract_value=fake.random_int(min=10_000, max=250_000, step=5000),
        )
        session.add(account)
        accounts.append(account)

    await session.flush()
    return accounts


async def create_identity_for_account(
    session: AsyncSession, *, tenant_id: uuid.UUID, account_id: uuid.UUID, user_count: int, fake: Faker
) -> list[IdentityMap]:
    """Creates user_count synthetic identity_map rows for one account
    (Decision D02 — every raw_events row must resolve through this
    table)."""

    identities = []
    for _ in range(user_count):
        row = IdentityMap(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            anonymous_id=f"anon-{uuid.uuid4().hex}",
            user_id=uuid.uuid4(),
            account_id=account_id,
        )
        session.add(row)
        identities.append(row)

    await session.flush()
    return identities


async def create_deal_for_account(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    hubspot_company_id: str,
    stage: str,
    amount: int,
    entered_stage_at: datetime,
    fake: Faker,
) -> StagingHubspotDeal:
    deal = StagingHubspotDeal(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        hubspot_deal_id=f"hs-deal-{uuid.uuid4().hex[:12]}",
        hubspot_company_id=hubspot_company_id,
        stage=stage,
        amount=amount,
        entered_stage_at=entered_stage_at,
    )
    session.add(deal)
    await session.flush()
    return deal
