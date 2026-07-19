import uuid

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    tenant_id: uuid.UUID
    dev_secret: str
