import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from meridian.api.middleware import RequestLoggingMiddleware
from meridian.api.routes.hubspot_oauth import hubspot_oauth_router
from meridian.api.routes.session import session_router
from meridian.api.routes.telemetry import telemetry_router
from meridian.api.routes.write_keys import write_keys_router
from meridian.logging_config import configure_logging

configure_logging()

app = FastAPI(title="Meridian API")

# Configure CORS for frontend dev origin
cors_allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True,
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(session_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(write_keys_router, prefix="/api/v1")
app.include_router(hubspot_oauth_router, prefix="/api/v1")
