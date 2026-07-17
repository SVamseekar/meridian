import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from meridian.db.base import Base


class StagingHubspotDeal(Base):
    """Generator-populated stand-in for HubSpot's inbound deal sync
    (Decision D04) until step 5's real sync exists."""

    __tablename__ = "staging_hubspot_deals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    hubspot_deal_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    hubspot_company_id: Mapped[str] = mapped_column(
        String, ForeignKey("staging_hubspot_companies.hubspot_company_id"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    entered_stage_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
