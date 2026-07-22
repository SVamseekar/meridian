import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from meridian.db.base import Base


class StagingHubspotCompany(Base):
    """HubSpot's inbound company sync staging table (Decision D04/D05).
    Multi-tenant scoped by tenant_id."""

    __tablename__ = "staging_hubspot_companies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "hubspot_company_id", name="uq_staging_hubspot_companies_tenant_company"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    hubspot_company_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    firm_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
