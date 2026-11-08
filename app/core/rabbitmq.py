"""RabbitMQ connectivity abstraction (pika, blocking connections — workers are separate
processes with their own blocking consume loops, so there's no need for an async client here;
this mirrors the project's sync-SQLAlchemy style throughout).

Step 1 only needs connectivity for the readiness check. Topology (exchanges/queues/DLX ladder —
see ARCHITECTURE.md §9) is declared starting the step that actually publishes/consumes messages,
not here — declaring unused topology now would be dead configuration with nothing to verify it
against.
"""

import logging

import pika
from pika.exceptions import AMQPError

from app.core.config import settings

logger = logging.getLogger("notifications.rabbitmq")


def get_connection() -> pika.BlockingConnection:
    """Open a new blocking connection. Callers are responsible for closing it — this is
    intentionally not a cached singleton, since pika connections aren't safe to share across
    threads/requests and a short-lived connection per use (or per worker-process-lifetime for
    long-running consumers) is the standard pika usage pattern.
    """
    if not settings.RABBITMQ_URL:
        raise RuntimeError("RABBITMQ_URL is not configured")
    params = pika.URLParameters(settings.RABBITMQ_URL)
    params.socket_timeout = 3
    return pika.BlockingConnection(params)


def ping() -> bool:
    """Used by the readiness check. Returns False (never raises) if RabbitMQ isn't configured or
    isn't reachable — readiness probes must report cleanly, not crash the request.
    """
    if not settings.RABBITMQ_URL:
        return False
    try:
        connection = get_connection()
        connection.close()
        return True
    except (AMQPError, OSError):
        logger.exception("RabbitMQ readiness check failed")
        return False
