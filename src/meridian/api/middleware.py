import json
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("meridian.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        latency_ms = round((time.monotonic() - start) * 1000, 2)

        payload = {
            "route": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
        }
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id

        logger.info(json.dumps(payload))
        return response
