import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meridian.api.schemas.session import SessionCreateRequest
from meridian.api.session import SESSION_COOKIE_NAME, SESSION_TOKEN_TTL_SECONDS, create_session_token
from meridian.db.models.tenant import Tenant
from meridian.db.session import get_async_session

logger = logging.getLogger("meridian.session")

session_router = APIRouter(tags=["session"])


@session_router.post("/session", status_code=204)
async def create_session(
    body: SessionCreateRequest,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    environment = os.environ.get("ENVIRONMENT", "development")
    if environment not in {"development", "test"}:
        logger.warning(
            '{"event": "session_bootstrap_attempted_in_production", "tenant_id": "%s"}',
            body.tenant_id,
        )
        raise HTTPException(status_code=404)

    dev_secret = os.environ.get("SESSION_DEV_SECRET")
    if dev_secret is None or body.dev_secret != dev_secret:
        raise HTTPException(status_code=401, detail="Invalid dev secret")

    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == body.tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    token = create_session_token(tenant.id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=os.environ.get("ENVIRONMENT", "development") != "development",
        samesite="lax",
        max_age=SESSION_TOKEN_TTL_SECONDS,
        path="/",
    )
