from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Notification Platform API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = False

    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "sqlite:///./notifications.db"

    # Redis — rate limiting, pub/sub for live dashboard updates. Optional in local dev without
    # Docker; required in testing/production (see core/redis_client.py).
    REDIS_URL: str | None = None

    # RabbitMQ — the actual message broker (see ARCHITECTURE.md §9 for topology). Optional in
    # local dev without Docker; required once notification processing (step 5+) exists.
    RABBITMQ_URL: str | None = None

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Rate limiting (requests per window per client) — in-memory for now, same documented
    # single-instance limitation Project 1 started with; Redis-backed per-org/channel limiting
    # is a dedicated later step (ARCHITECTURE.md roadmap step 9), not implemented yet.
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Worker tuning
    NOTIFICATION_WORKER_PREFETCH: int = 10
    OUTBOX_POLL_INTERVAL_SECONDS: float = 2.0
    OUTBOX_MAX_ATTEMPTS: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
