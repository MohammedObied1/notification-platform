# Distributed Notification Platform — Architecture Plan

Project 2 of 3. Status: **planning complete, Step 1 not yet started.**

## 1. Overview

A multi-tenant notification infrastructure (conceptually a simplified SendGrid/Twilio/OneSignal):
external applications integrate via a REST API + API key, submit notifications, and get an
immediate `202 Accepted` while the actual send happens asynchronously through a message broker and
a pool of workers. The system's priority order is **delivery reliability > tenant isolation >
observability > features** — a notification must never be silently lost, one tenant must never see
another's data, and every status transition must be inspectable.

This project is designed to eventually receive events from Project 1's transactional outbox
(`digital-wallet/workers/outbox_worker.py` currently just logs — see that project's
ARCHITECTURE.md §6), though no code coupling exists between the two repos; the interface is just
"an HTTP call to `POST /api/v1/notifications`."

## 2. Main Entities

| Entity | Purpose |
|---|---|
| `Organization` | Tenant boundary. Everything else belongs to exactly one organization. |
| `OrgUser` | A dashboard user belonging to an organization (role: `owner`/`member`), separate from the API-key-authenticated traffic that actually sends notifications. |
| `ApiKey` | `ntf_<random>` bearer credential scoped to one organization, with scopes, rotation, and revocation. Only the hash is stored. |
| `Template` | Reusable content with `{{variable}}` placeholders, versioned, one body per channel. |
| `NotificationPreference` | Per-recipient, per-category (`security`/`transactional`/`marketing`/`reminders`) opt-in/out, per channel. Security notifications can bypass opt-out (configurable). |
| `Notification` | One send request: recipient, channel, template (or raw content), variables, status, timestamps, scheduled-for time. |
| `NotificationAttempt` | One delivery attempt against a provider — success/failure, latency, error detail. A `Notification` can have several (retries). |
| `WebhookEndpoint` | A tenant's URL to receive status-change callbacks, with a signing secret. |
| `WebhookDelivery` | One outbound webhook POST attempt — status, response code, retry count. |
| `UsageCounter` | Per-org, per-channel, per-period counters for quota/rate-limit enforcement. |
| `DeadLetterEntry` | A `Notification` that exhausted all retries, surfaced for admin inspection/manual retry. |
| `OutboxEvent` | Written in the same DB transaction as a new `Notification` row; a separate publisher moves it to RabbitMQ and marks it dispatched — see §7/§8 for why this project uses an outbox *and* a real broker, unlike Project 1 which only needed the former. |

## 3. Database Schema (proposal)

```
organizations(id, name, slug UNIQUE, created_at)

org_users(id, org_id FK, email UNIQUE, password_hash, role[owner|member], is_active, created_at)

api_keys(id, org_id FK, name, key_prefix, key_hash UNIQUE, scopes JSON, is_active,
         last_used_at, created_at, revoked_at)
  -- only key_hash is stored; the raw key is shown once at creation time, like GitHub PATs

templates(id, org_id FK, name, channel[email|sms|push|in_app|webhook], version,
          subject, body, variables JSON, is_active, created_at)
  -- UNIQUE(org_id, name, channel, version); the "current" version per (org_id, name, channel)
  -- is the highest version with is_active=true

notification_preferences(id, org_id FK, recipient, category[security|transactional|marketing|reminders],
                          channel, enabled, updated_at)
  -- UNIQUE(org_id, recipient, category, channel)

notifications(id, org_id FK, recipient, channel, category, template_id FK NULL,
              variables JSON, rendered_subject, rendered_body,
              status[created|queued|processing|sent|delivered|failed|retrying|cancelled],
              scheduled_for, idempotency_key, attempt_count, max_attempts,
              created_at, queued_at, sent_at, delivered_at, failed_at)
  -- INDEX(org_id, created_at DESC); INDEX(status, scheduled_for) for the scheduler sweep
  -- UNIQUE(org_id, idempotency_key) WHERE idempotency_key IS NOT NULL

notification_attempts(id, notification_id FK, provider, attempt_number, status[success|failure],
                       latency_ms, error_message, created_at)

webhook_endpoints(id, org_id FK, url, secret, is_active, created_at)

webhook_deliveries(id, webhook_endpoint_id FK, notification_id FK, status[pending|delivered|failed],
                    response_code, attempt_count, created_at, delivered_at)

usage_counters(id, org_id FK, channel, period_start, period_end, count)
  -- UNIQUE(org_id, channel, period_start)

dead_letters(id, notification_id FK UNIQUE, reason, failed_at, retried_at, retried_by FK NULL)

outbox_events(id, notification_id FK, payload JSON, dispatched_at NULL, attempts, created_at)
  -- INDEX(dispatched_at) WHERE dispatched_at IS NULL — the outbox_publisher's poll query
```

Indexing choices worth calling out up front: `notifications(status, scheduled_for)` is the one the
scheduler sweep hits every poll interval, so it needs to be a composite index, not two separate
ones; tenant isolation means almost every other query is already filtered by `org_id` first, so
`org_id` leads every other composite index in this schema.

## 4. API Modules

| Module | Endpoints |
|---|---|
| `auth` | org signup, dashboard login/refresh (JWT, for the React dashboard only) |
| `api-keys` | create (shows raw key once), list, rotate, revoke |
| `notifications` | create (`202`), get, list/search (filters: status, channel, recipient, date range), cancel (if still scheduled) |
| `templates` | CRUD + version history |
| `preferences` | get/set per-recipient preferences |
| `webhooks` | CRUD webhook endpoints, list deliveries, retry a failed delivery |
| `dead-letters` | list, inspect, manual retry |
| `usage` | current-period usage per channel (quota dashboard) |
| `admin/stats` | aggregate delivery stats for the dashboard |
| `health` | `/health`, `/api/v1/health`, `/api/v1/health/ready` (matches Project 1's pattern) |
| `ws` / `events` | WebSocket (or SSE fallback) stream of status changes for the dashboard |

## 5. Backend Folder Structure

```
app/
  core/        config, database, security (JWT for dashboard, API-key hashing), exceptions,
               middleware, logging
  models/      organization, org_user, api_key, template, preference, notification,
               notification_attempt, webhook, usage, dead_letter
  schemas/     pydantic request/response models per module
  services/    auth, api_key, template, notification (create/render/enqueue), preference,
               webhook, usage, dead_letter
  providers/   NotificationProvider protocol + email/sms/push/in_app/webhook adapters
               (mock implementations now; real providers are a config swap later)
  api/v1/      routers — translate HTTP only, no business rules
  main.py
workers/       notification_worker.py (consumes the queue, calls a provider, records the attempt),
               webhook_worker.py (delivers webhook callbacks with signing/retry),
               scheduler.py (sweeps notifications whose scheduled_for has arrived and enqueues them)
alembic/       migrations
scripts/       seed.py
tests/         unit + integration + queue/retry/DLQ + tenant-isolation tests
frontend/      React + TS + Vite tenant dashboard — see module list below
```

**Frontend modules** (`frontend/src/`, same layout convention as `pages/`, `components/`,
`layouts/`, `routes/`, `api/`, `auth/`, `hooks/`, `types/`, `utils/` Project 1 used). Full page set,
built incrementally as the backend for each supports it (roadmap §12): login, overview (sent
today/delivery rate/failures/channel breakdown), notification explorer + detail, templates,
API keys, providers, webhooks, scheduled notifications, DLQ, usage analytics, team/organization,
settings — with TanStack Query for data fetching and a WebSocket/SSE hook for live status updates,
mirroring the route-guard and loading/error/empty-state conventions `digital-wallet/frontend`
already established. Step 1 builds only the shell (layout, 404, a status page hitting `/health` +
`/health/ready`) — no tenant pages yet, since there's no auth or tenant data to show.

Request flow: `Router → Service → Repository/Models → PostgreSQL`, with `POST /notifications`
additionally publishing to the broker *after* its own DB commit (see §7) rather than inside it.

## 6. Infrastructure Components

- **PostgreSQL** — system of record for organizations, templates, notification history, and
  delivery/audit trail.
- **RabbitMQ** — the actual message broker that *distributes and retries* notification work.
  Chosen over Kafka because this is a task queue with per-message retry/DLQ semantics, not a
  replayable event log — AMQP's native dead-lettering and per-queue TTL map directly onto this
  project's retry/DLQ requirements, where Kafka would need that machinery hand-built on top of
  consumer groups and offsets.
- **PostgreSQL outbox** — the durability anchor *in front of* RabbitMQ. `POST /notifications`
  writes the `notifications` row and an `outbox_events` row in one DB transaction (the pattern
  the spec calls for explicitly, and the one Project 1 already uses for its own async events).
  A separate, lightweight **outbox publisher** reads pending outbox rows and publishes them to
  RabbitMQ, then marks them dispatched. This is deliberately different from Project 1's choice to
  publish after commit with no outbox table: there, the "broker" was an in-house polling table, so
  an outbox *in front of* it would have been redundant. Here RabbitMQ is a real external system
  that can be briefly unreachable, so the outbox is what makes "the DB row exists" and "the queue
  will eventually see it" true independently of RabbitMQ's availability at the exact moment of the
  HTTP request — see §7 for the full flow and §9 for the exact topology.
- **Redis** — tenant/provider rate limiting (sliding window, shared across worker replicas — the
  thing Project 1 explicitly deferred for its own single-instance rate limiter), and the pub/sub
  backbone for the dashboard's live WebSocket/SSE updates (a worker publishes a status change; the
  API process subscribed to that channel forwards it to connected dashboard clients).
- **Docker Compose** — postgres, redis, rabbitmq, api, outbox-publisher, notification-worker,
  webhook-worker, scheduler, frontend (built into the api image, same pattern as Project 1).

## 7. Notification Lifecycle Flow

```mermaid
sequenceDiagram
    participant C as Client (API key)
    participant R as FastAPI
    participant DB as PostgreSQL
    participant OP as outbox_publisher
    participant MQ as RabbitMQ
    participant W as notification_worker
    participant P as Provider adapter

    C->>R: POST /api/v1/notifications (Idempotency-Key)
    R->>DB: BEGIN; INSERT notifications(status=CREATED); INSERT outbox_events; COMMIT
    R-->>C: 202 Accepted (notification_id)

    loop poll
        OP->>DB: SELECT ... FOR UPDATE SKIP LOCKED (pending outbox_events)
        OP->>MQ: publish to notifications.exchange (routing key = channel.priority)
        OP->>DB: UPDATE outbox_events SET dispatched_at = now()
    end

    MQ->>W: deliver message (manual ack)
    W->>DB: UPDATE notifications SET status=PROCESSING (guarded: only if still QUEUED)
    W->>P: send(recipient, rendered content)
    alt success
        P-->>W: ok
        W->>DB: UPDATE notifications SET status=SENT; INSERT notification_attempts
        W->>MQ: ack
    else transient failure
        P-->>W: error (timeout/429/5xx)
        W->>DB: UPDATE notifications SET status=RETRYING; INSERT notification_attempts
        W->>MQ: nack -> publish to notifications.retry.<n>s (TTL+DLX ladder, §9)
    else permanent failure or attempts exhausted
        W->>DB: UPDATE notifications SET status=FAILED; INSERT dead_letters
        W->>MQ: publish to notifications.dlq; ack original
    end
```

**Why the outbox sits in front of RabbitMQ instead of publishing directly in the request**: if the
API process published straight to RabbitMQ inside (or right after) the HTTP request and RabbitMQ
was briefly unreachable, the client would either get a `5xx` for something that should have been
a reliable `202`, or — worse — get `202` while silently dropping the message. The outbox makes
"durably accepted" and "will reach the broker" two separate, independently-retryable guarantees:
the HTTP response only depends on the Postgres commit (fast, always-on, same DB the request already
needed anyway); the outbox publisher retries against RabbitMQ on its own schedule, invisibly to
the client.

## 8. Worker Model

Three worker processes, each horizontally scalable, each independent of API process restarts:

| Worker | Reads from | Does | Concurrency safety |
|---|---|---|---|
| `outbox_publisher` | `outbox_events` (Postgres) | Publishes pending events to RabbitMQ, marks dispatched | `SELECT ... FOR UPDATE SKIP LOCKED` — multiple replicas partition the backlog instead of double-publishing |
| `notification_worker` | `notifications.queue` (RabbitMQ) | Renders template, calls the provider adapter, records the attempt, transitions status | Manual ack only after the DB status transition commits; a crash before ack means RabbitMQ redelivers — the worker re-checks status before acting (idempotent-by-status-check), so a redelivery of an already-`SENT` message is a safe no-op, not a double-send |
| `scheduler` | `notifications` (Postgres, `scheduled_for <= now()`) | Sweeps due scheduled notifications and hands them to the outbox the same way a fresh `POST` would | `SELECT ... FOR UPDATE SKIP LOCKED` on the due rows — multiple scheduler replicas never double-publish the same scheduled notification |

`consumer_prefetch` (RabbitMQ QoS) is configurable per worker so one slow notification can't starve
a replica's whole prefetch buffer; default is modest (10) and documented as a tuning knob in
`.env.example`, not hardcoded.

## 9. RabbitMQ Topology

```
notifications.exchange            (topic, durable)
  ├─ routing key "email.normal"  ─┐
  ├─ routing key "sms.critical"  ─┼─> notifications.queue (durable, quorum queue)
  ├─ routing key "push.*"        ─┘      consumed by: notification_worker (N replicas)
  │
  └─ (priority is a routing-key segment, not a queue-per-tenant or queue-per-priority split —
      the spec explicitly warns against a queue per tenant; RabbitMQ's native per-message
      `priority` property on a single priority-enabled queue handles CRITICAL-jumps-the-line
      without multiplying queues)

notifications.retry.30s / .1m / .2m / .4m / .8m   (durable queues, no consumers)
  each has:
    x-message-ttl = <delay>
    x-dead-letter-exchange = notifications.exchange
    x-dead-letter-routing-key = <original routing key>
  -> a nacked message is republished here; when its TTL expires, RabbitMQ auto-dead-letters it
     back onto notifications.exchange with the same routing key, landing in notifications.queue
     again for another attempt — this is the "TTL+DLX ladder" the spec calls out as the preferred
     retry-scheduling design, chosen over a Redis scheduler because it needs no separate polling
     process and RabbitMQ already guarantees the message isn't lost while delayed.

notifications.dlq.exchange (fanout, durable) -> notifications.dlq (durable)
  -> terminal queue for attempts-exhausted / permanently-classified failures; consumed only by the
     admin "manually retry" action (republishes to notifications.exchange) or left for inspection.

webhooks.exchange / webhooks.queue / webhooks.retry.* / webhooks.dlq
  -> identical ladder shape, separate exchange, consumed by webhook_worker — kept separate from
     notification delivery so a webhook-receiving tenant's flaky endpoint can never create backlog
     that delays actual notification sending.
```

Durable exchanges/queues + persistent messages (`delivery_mode=2`) throughout, so a RabbitMQ
restart doesn't lose anything sitting in a queue.

## 10. Security Strategy

- **External API traffic**: `Authorization: Bearer ntf_<key>` — only the key's hash is stored
  (same `passlib` hashing Project 1 uses for passwords), looked up by a fast prefix index
  (`key_prefix`) then verified against the hash, not a linear scan.
- **Dashboard traffic**: JWT access/refresh, same pattern as Project 1, scoped to `OrgUser`.
- **Tenant isolation**: every query is scoped by `org_id` derived from the authenticated
  principal (the API key's org, or the JWT's org) — never accepted as a client-supplied field.
  This is the single most security-critical invariant in a multi-tenant system and gets dedicated
  tests (`test_tenant_isolation.py`) from day one, not bolted on later.
- **Webhook signing**: every outbound webhook POST carries an `X-Signature` HMAC (secret per
  `WebhookEndpoint`) so the receiving tenant app can verify authenticity — mirrors how Stripe/GitHub
  webhooks work.
- **Idempotency**: `POST /notifications` accepts an optional `Idempotency-Key`, scoped per
  `org_id` (learning directly from Project 1's cross-user idempotency bug — this project scopes it
  correctly from the start).
- **Rate limiting**: Redis-backed, per `org_id` + channel, returns `429` with `Retry-After`.

## 11. Testing Strategy

- **Unit tests**: template rendering/validation, provider adapter interface, backoff calculation.
- **Integration tests** (SQLite or a lightweight broker fake): full HTTP flow —
  create org → issue API key → send notification → `202` → worker picks it up → status transitions.
- **Queue/retry/DLQ tests**: a provider adapter that fails N times then succeeds; assert the
  backoff schedule and that the Nth failure (beyond `max_attempts`) produces a `DeadLetterEntry`
  and stops retrying.
- **Tenant isolation tests**: org A's API key must never be able to read/list/cancel org B's
  notifications, templates, or webhook endpoints — attempted directly, not just "not shown in the
  UI."
- **Idempotency tests**: duplicate `Idempotency-Key` within an org → one notification; same key,
  different org → both succeed independently.
- **Webhook tests**: signature verification, retry-with-backoff on a non-2xx response, timeout
  handling.
- **Real-broker tests**: gated behind a `RABBITMQ_TEST_URL` the same way Project 1 gates its
  real-Postgres concurrency tests — this sandboxed environment has no Docker, so these run in CI
  against a `rabbitmq:3-management-alpine` service container, not locally.

## 12. Development Roadmap

1. ⬜ **Project scaffolding** — repo layout, config, DB/session setup, Alembic, Docker, CI, health
   checks, base test harness, frontend shell. *(Step 1 — next)*
2. ⬜ Organizations, API keys (create/rotate/revoke), dashboard auth (JWT for `OrgUser`).
3. ⬜ Templates (CRUD, versioning, variable validation).
4. ⬜ Notification create endpoint — validation + `202` + DB row, no queue yet (prove the shape).
5. ⬜ RabbitMQ integration + `notification_worker` — the core async pipeline, mock provider adapters.
6. ⬜ Retry backoff + Dead Letter Queue + admin DLQ inspection/retry.
7. ⬜ Notification preferences (opt-in/out per category/channel).
8. ⬜ Scheduled notifications + `scheduler` worker + cancellation.
9. ⬜ Rate limiting (Redis) per org/channel.
10. ⬜ Webhook delivery — signing, retries, delivery log, admin webhook management.
11. ⬜ Idempotency on notification creation (org-scoped from the start).
12. ⬜ Admin/tenant dashboard APIs — stats, usage, search/filter.
13. ⬜ Real-time updates — WebSocket/SSE status stream (Redis pub/sub backed).
14. ⬜ Frontend dashboard (React + TS + Vite) — mirrors Project 1's admin dashboard conventions.
15. ⬜ Reliability/concurrency/tenant-isolation test hardening + seed data + deployment readiness.

Each step ends with: what was implemented, files changed, tests added, verification commands run,
test results, remaining work, and a suggested commit message — before moving to the next step,
exactly as Project 1 was run.
