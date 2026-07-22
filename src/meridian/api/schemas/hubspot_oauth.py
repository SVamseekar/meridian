from datetime import datetime

from pydantic import BaseModel


class HubSpotConnectionStatus(BaseModel):
    connected: bool
    connected_at: datetime | None


class HubSpotSyncStatus(BaseModel):
    """Durable sync-health signal, distinct from HubSpotConnectionStatus: a
    tenant can have a valid credentials row (still "connected") while every
    scheduled sync/refresh has been failing (e.g. revoked HubSpot access).
    Returns 404 (via the route) if the tenant has never connected."""

    hubspot_portal_id: str | None
    scopes: list[str] | None
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_sync_error: str | None


class HubSpotWebhookResponse(BaseModel):
    status: str
    processed: int
