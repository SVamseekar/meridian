import base64
import hashlib
import hmac
import logging
import os
import time
from urllib.parse import quote

logger = logging.getLogger(__name__)

MAX_TIMESTAMP_AGE_MS = 300000  # 5 minutes


def verify_hubspot_v3_signature(
    signature: str | None,
    timestamp: str | None,
    method: str,
    uri: str,
    body: str,
    client_secret: str | None = None,
) -> bool:
    """Verify HubSpot v3 webhook signature (X-HubSpot-Signature-v3)."""
    if not signature or not timestamp:
        logger.warning("Webhook missing signature or timestamp header")
        return False

    secret = client_secret or os.environ.get("HUBSPOT_WEBHOOK_SECRET") or os.environ.get("HUBSPOT_CLIENT_SECRET")
    if not secret:
        logger.error("No webhook client secret configured for signature verification")
        return False

    # Check timestamp freshness to prevent replay attacks
    try:
        ts_ms = int(timestamp)
        now_ms = int(time.time() * 1000)
        if abs(now_ms - ts_ms) > MAX_TIMESTAMP_AGE_MS:
            logger.warning("Webhook timestamp out of allowed range: timestamp=%s now=%s", ts_ms, now_ms)
            return False
    except ValueError:
        logger.warning("Invalid webhook timestamp format: %s", timestamp)
        return False

    # Construct v3 signature string: METHOD + URI + BODY + TIMESTAMP
    source_string = f"{method.upper()}{uri}{body}{timestamp}"
    key_bytes = secret.encode("utf-8")
    data_bytes = source_string.encode("utf-8")

    computed_hash = hmac.new(key_bytes, data_bytes, hashlib.sha256).digest()
    computed_signature = base64.b64encode(computed_hash).decode("utf-8")

    return hmac.compare_digest(computed_signature, signature)
