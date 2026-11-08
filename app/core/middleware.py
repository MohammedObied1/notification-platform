import logging
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger("notifications.request")

_HEALTH_PATHS = {"/health", "/api/v1/health", "/api/v1/health/ready", "/docs", "/openapi.json", "/redoc"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Adds a request ID + timing header and logs every request. The request ID doubles as the
    correlation ID referenced throughout ARCHITECTURE.md's observability section — a client can
    pass its own via X-Request-ID and it will be echoed back and logged, so a support request can
    be traced from a client log line straight to the matching server-side log line.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        logger.info("%s %s -> %s (%.1fms) rid=%s", request.method, request.url.path, response.status_code, duration_ms, request_id)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding-window rate limiter keyed by client IP.

    Single-instance only, same documented limitation Project 1 started with — a Redis-backed,
    per-organization/per-channel limiter is a dedicated later roadmap step (ARCHITECTURE.md §12
    step 9), not something to half-build here before organizations/API keys even exist.
    """

    def __init__(self, app: FastAPI, limit: int, window_seconds: int) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _HEALTH_PATHS:
            return await call_next(request)

        client = request.client.host if request.client else "anonymous"
        now = time.monotonic()
        hits = self._hits[client]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return JSONResponse(status_code=429, content={"detail": "Too many requests"}, headers={"Retry-After": str(self.window)})
        hits.append(now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(self.limit - len(hits))
        return response


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestContextMiddleware)
    if settings.ENVIRONMENT != "testing":
        app.add_middleware(RateLimitMiddleware, limit=settings.RATE_LIMIT_REQUESTS, window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS)
