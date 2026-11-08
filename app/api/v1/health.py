import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.api.deps import DBSession
from app.core import rabbitmq, redis_client
from app.core.config import settings

logger = logging.getLogger("notifications.health")

router = APIRouter(tags=["Health"])
versioned_router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/health", summary="Combined liveness & readiness probe (used by Docker HEALTHCHECK)")
def health(db: DBSession) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__, "database": "connected"}


@versioned_router.get("", summary="Liveness probe — process is up, no dependency checks")
def liveness() -> dict:
    return {"status": "ok"}


@versioned_router.get("/ready", summary="Readiness probe — verifies PostgreSQL, Redis, and RabbitMQ")
def readiness(db: DBSession):
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except SQLAlchemyError:
        logger.exception("readiness check failed: database unreachable")
        checks["database"] = "disconnected"

    # Redis/RabbitMQ are optional in local dev without Docker (see Settings' docstrings) — "not
    # configured" is reported distinctly from "configured but unreachable" so a developer running
    # without them locally doesn't get a misleading "unavailable" for something they opted out of.
    if settings.REDIS_URL:
        checks["redis"] = "connected" if redis_client.ping() else "disconnected"
    else:
        checks["redis"] = "not configured"

    if settings.RABBITMQ_URL:
        checks["rabbitmq"] = "connected" if rabbitmq.ping() else "disconnected"
    else:
        checks["rabbitmq"] = "not configured"

    critical_down = any(v == "disconnected" for v in checks.values())
    if critical_down:
        return JSONResponse(status_code=503, content={"status": "unavailable", **checks})
    return {"status": "ready", **checks}
