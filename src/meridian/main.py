from fastapi import FastAPI

from meridian.api.middleware import RequestLoggingMiddleware
from meridian.api.routes.telemetry import telemetry_router
from meridian.api.routes.write_keys import write_keys_router
from meridian.logging_config import configure_logging

configure_logging()

app = FastAPI(title="Meridian API")
app.add_middleware(RequestLoggingMiddleware)

app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(write_keys_router, prefix="/api/v1")
