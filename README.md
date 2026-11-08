# Notification Platform API

A production-style **multi-tenant distributed notification platform** built with FastAPI,
SQLAlchemy 2.0, PostgreSQL, RabbitMQ, and Redis. External applications integrate via API key,
submit notifications, and get an immediate `202 Accepted` while delivery happens asynchronously
through a message broker and a worker pool — supporting email, SMS, push, in-app, and webhook
channels with retries, a dead letter queue, idempotency, rate limiting, and scheduled delivery.

This is Project 2 of a 3-project portfolio series; Project 1 ([`digital-wallet`](https://github.com/MohammedObied1/digital-wallet))
is a separate, complete, unmodified application. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the
full design: entities, schema, RabbitMQ topology, worker model, security strategy, and the
complete step-by-step roadmap.

**Status:** Step 1 of 15 — project foundation only (config, DB, health/readiness checks covering
Postgres/Redis/RabbitMQ, Docker, CI, a minimal frontend shell). No organizations, API keys,
templates, or notification business logic exist yet — those land in the steps that follow.

## Repository structure

```
app/           FastAPI backend — core/, models/, schemas/, services/, providers/, api/v1/
workers/       background workers (empty until Step 5+ — see ARCHITECTURE.md §12)
alembic/       database migrations
scripts/       seed.py (added once there's data worth seeding)
tests/         pytest suite
frontend/      React + TS + Vite dashboard
```

---

## Quick start

### Backend (SQLite, no Docker needed for Step 1)

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for interactive Swagger UI.

`GET /health` is a combined liveness+readiness check (used by Docker's `HEALTHCHECK`).
`GET /api/v1/health` is pure liveness. `GET /api/v1/health/ready` checks PostgreSQL, Redis, and
RabbitMQ individually — each reports `connected` / `disconnected` / `not configured` (Redis and
RabbitMQ are optional for local development without Docker; see `.env.example`).

### Frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173, proxies /api to http://localhost:8000
```

Currently just a status page showing the three readiness checks above — there's no auth or tenant
data yet for a real dashboard to show.

### Docker (PostgreSQL + Redis + RabbitMQ + API)

```bash
docker compose up --build
```

Brings up Postgres, Redis, RabbitMQ (management UI at http://localhost:15672, guest/guest), and
the API (migrations run automatically on container start). The frontend is built into the API
image and served from the same container — no separate frontend container, same pattern as
Project 1. Worker containers are added to `docker-compose.yml` starting the roadmap step that
implements each worker.

### Tests

```bash
pytest                         # backend tests + coverage report
ruff check app tests           # backend lint
ruff format --check app tests  # backend format check
cd frontend && npx tsc -b      # frontend typecheck
cd frontend && npm run lint    # frontend lint (oxlint)
cd frontend && npm run build   # frontend production build
```

### Database migrations

```bash
alembic upgrade head
alembic downgrade base
alembic revision --autogenerate -m "description"   # after adding/changing a model
alembic check                                        # confirm no drift
```

## Environment variables

See [`.env.example`](.env.example) for the full list with defaults. `DATABASE_URL` defaults to
SQLite for local dev; `REDIS_URL`/`RABBITMQ_URL` are optional locally and required in
Docker/production.

## Known limitations (Step 1)

- No authentication, organizations, or API keys yet.
- No notification business logic, workers, or queue processing yet.
- Rate limiting is in-memory, single-instance (same documented starting point Project 1 used
  before its own hardening pass) — Redis-backed, per-organization limiting is a dedicated later
  step, not implemented yet.

## License

MIT
