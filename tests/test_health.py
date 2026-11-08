def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_versioned_liveness(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_versioned_readiness_without_redis_or_rabbitmq_configured(client):
    """In the default test environment, REDIS_URL/RABBITMQ_URL are unset — readiness must report
    that distinctly as "not configured" rather than treating it as a failure (see health.py).
    """
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["database"] == "connected"
    assert body["redis"] == "not configured"
    assert body["rabbitmq"] == "not configured"


def test_versioned_readiness_reports_503_when_a_configured_dependency_is_down(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6399/0")  # nothing listens here
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 503
    assert r.json()["redis"] == "disconnected"
