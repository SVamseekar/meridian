import json
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("meridian.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = None
        exception_to_raise = None
        try:
            response = await call_next(request)
        except Exception as exc:
            exception_to_raise = exc
        finally:
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            status_code = response.status_code if response is not None else 500

            payload = {
                "route": request.url.path,
                "status_code": status_code,
                "latency_ms": latency_ms,
            }
            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id is not None:
                payload["tenant_id"] = str(tenant_id)

            logger.info(json.dumps(payload))

        if exception_to_raise is not None:
            raise exception_to_raise
        return response
