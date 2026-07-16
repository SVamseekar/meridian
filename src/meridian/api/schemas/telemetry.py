from datetime import datetime

from pydantic import BaseModel, Field


class TelemetryEventIn(BaseModel):
    anonymous_id: str
    event_name: str
    properties: dict = Field(default_factory=dict)
    client_timestamp: datetime
    # Note: any "tenant_id" field a client sends is NOT part of this model —
    # Pydantic ignores unknown fields by default, and tenant_id is always
    # server-resolved from the write key (Decision D08/D14).


class TelemetryEventAck(BaseModel):
    status: str = "accepted"
