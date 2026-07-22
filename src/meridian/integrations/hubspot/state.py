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


def create_oauth_state_token(tenant_id: uuid.UUID) -> tuple[str, str]:
    """Returns (state_jwt, nonce). The nonce is also embedded (signed) in the
    JWT, but the caller must additionally bind it to the initiating browser
    (e.g. an HttpOnly cookie set alongside the redirect) and require the
    callback to present the same nonce via `decode_oauth_state_token`'s
    `expected_nonce`. Without that binding, a leaked state token (referrer
    header, browser history, logs) would let anyone complete the callback
    for that tenant within the token's TTL — the nonce binding closes that
    gap by requiring possession of the cookie set on the same browser/request
    that started the flow, not just the token itself."""
    now = int(time.time())
    nonce = uuid.uuid4().hex
    claims = {
        "tenant_id": str(tenant_id),
        "nonce": nonce,
        "iat": now,
        "exp": now + OAUTH_STATE_TTL_SECONDS,
    }
    return jwt.encode(claims, _state_secret(), algorithm=_ALGORITHM), nonce


def decode_oauth_state_token(token: str, expected_nonce: str | None = None) -> uuid.UUID:
    try:
        claims = jwt.decode(token, _state_secret(), algorithms=[_ALGORITHM])
        if expected_nonce is not None and claims.get("nonce") != expected_nonce:
            raise InvalidOAuthStateError("OAuth state nonce does not match session")
        return uuid.UUID(claims["tenant_id"])
    except (JWTError, KeyError, ValueError) as exc:
        raise InvalidOAuthStateError("Invalid or expired OAuth state") from exc
