from datetime import datetime

from pydantic import BaseModel


class HubSpotConnectionStatus(BaseModel):
    connected: bool
    connected_at: datetime | None
