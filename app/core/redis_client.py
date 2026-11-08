"""Thin Redis connectivity wrapper. Nothing in this project talks to `redis` directly outside
this module — a single choke point makes it possible to see every real usage in one place (the
rate limiter and pub/sub are added in later roadmap steps; this module's job for Step 1 is just
"can we reach Redis", for the readiness check).
"""

from functools import lru_cache

import redis

from app.core.config import settings


@lru_cache
def get_redis_client() -> "redis.Redis | None":
    """Returns a Redis client, or None if REDIS_URL isn't configured (allowed in local dev
    without Docker — see Settings.REDIS_URL's docstring). Callers must handle the None case.
    """
    if not settings.REDIS_URL:
        return None
    return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)


def ping() -> bool:
    """Used by the readiness check. Returns False (never raises) if Redis isn't configured or
    isn't reachable — readiness probes must report cleanly, not crash the request.
    """
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except redis.RedisError:
        return False
