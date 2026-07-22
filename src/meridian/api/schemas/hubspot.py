from datetime import datetime
from pydantic import BaseModel


class HubspotConnectResponse(BaseModel):
    authorize_url: str


class HubspotStatusResponse(BaseModel):
    connected: bool
    hubspot_portal_id: str | None = None
    scopes: list[str] | None = None
    connected_at: datetime | None = None
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None


class HubspotWebhookResponse(BaseModel):
    status: str
    processed: int
