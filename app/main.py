from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.router import api_router
from app.api.v1 import health
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middleware

DESCRIPTION = """
**Notification Platform API** is a multi-tenant distributed notification system: external
applications integrate via API key, submit notifications, and get an immediate `202 Accepted`
while delivery happens asynchronously through RabbitMQ and a worker pool.

## Status
Step 1 of the roadmap (see ARCHITECTURE.md) — project foundation only. No organizations, API
keys, or notification business logic exist yet.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # In the Docker image the frontend is pre-built into frontend/dist; mounting it here lets a
    # single container serve both the API and the UI (same pattern as digital-wallet).
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()
