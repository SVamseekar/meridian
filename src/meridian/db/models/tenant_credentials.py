import uuid
from datetime import datetime

from sqlalchemy import ARRAY, LargeBinary, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from meridian.db.base import Base


class TenantCredentials(Base):
    """OAuth/API credentials per tenant per provider. See Decision D09."""

    __tablename__ = "tenant_credentials"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    provider: Mapped[str] = mapped_column(String, primary_key=True)

    hubspot_portal_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    access_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scopes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Durable sync-health signal, distinct from row existence: a tenant can
    # have a valid credentials row (still "connected") while every scheduled
    # sync/refresh has been failing (e.g. revoked HubSpot access) — status
    # endpoints must be able to tell those apart instead of only checking
    # whether this row exists.
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String, nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
