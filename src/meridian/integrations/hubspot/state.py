import os
import time
import uuid

from jose import JWTError, jwt

OAUTH_STATE_TTL_SECONDS = 600  # 10 minutes — enough for a user to complete HubSpot's consent screen
_ALGORITHM = "HS256"


class InvalidOAuthStateError(Exception):
    """Raised when an OAuth state token is missing, malformed, expired, or
    has an invalid signature. Callers should treat this as a rejected
    callback (log and redirect with an error), never leak which specific
    failure occurred."""


def _state_secret() -> str:
    return os.environ["HUBSPOT_OAUTH_STATE_SECRET"]


def create_oauth_state_token(tenant_id: uuid.UUID) -> str:
    now = int(time.time())
    claims = {
        "tenant_id": str(tenant_id),
        "nonce": uuid.uuid4().hex,
        "iat": now,
        "exp": now + OAUTH_STATE_TTL_SECONDS,
    }
    return jwt.encode(claims, _state_secret(), algorithm=_ALGORITHM)


def decode_oauth_state_token(token: str) -> uuid.UUID:
    try:
        claims = jwt.decode(token, _state_secret(), algorithms=[_ALGORITHM])
        return uuid.UUID(claims["tenant_id"])
    except (JWTError, KeyError, ValueError) as exc:
        raise InvalidOAuthStateError("Invalid or expired OAuth state") from exc
