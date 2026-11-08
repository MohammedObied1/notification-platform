import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """Structured-enough logging foundation for Step 1. Later steps add contextual fields
    (organization_id, notification_id, attempt_id, provider, channel, worker_id,
    correlation_id — see ARCHITECTURE.md's observability section) via a logging filter/adapter
    once there's something to attach those fields to; wiring that now would just produce log
    lines with empty placeholders.
    """
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("notifications").setLevel(level)
    logging.getLogger("notifications.startup").info("logging configured (level=%s)", logging.getLevelName(level))
