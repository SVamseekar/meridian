import os
import time
import uuid

from jose import JWTError, jwt

SESSION_COOKIE_NAME = "meridian_session"
SESSION_TOKEN_TTL_SECONDS = 3600  # 1 hour — D16, no refresh/revocation at this scope
_ALGORITHM = "HS256"


class InvalidSessionTokenError(Exception):
    """Raised when a session token is missing, malformed, expired, or has
    an invalid signature. Callers should treat this as an unauthenticated
    request (401), never leak which specific failure occurred."""


def _session_secret() -> str:
    return os.environ["SESSION_SECRET"]


def create_session_token(tenant_id: uuid.UUID) -> str:
    now = int(time.time())
    claims = {
        "tenant_id": str(tenant_id),
        "iat": now,
        "exp": now + SESSION_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(claims, _session_secret(), algorithm=_ALGORITHM)


def decode_session_token(token: str) -> uuid.UUID:
    try:
        claims = jwt.decode(token, _session_secret(), algorithms=[_ALGORITHM])
        return uuid.UUID(claims["tenant_id"])
    except (JWTError, KeyError, ValueError) as exc:
        raise InvalidSessionTokenError("Invalid or expired session token") from exc
