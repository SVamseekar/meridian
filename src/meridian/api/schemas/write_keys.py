import uuid
from datetime import datetime

from pydantic import BaseModel


class WriteKeyCreated(BaseModel):
    id: uuid.UUID
    key: str  # plaintext, shown exactly once
    created_at: datetime


class WriteKeyMasked(BaseModel):
    id: uuid.UUID
    masked_key: str  # e.g. "wk_live_••••••••1a2b"
    created_at: datetime
    revoked_at: datetime | None
