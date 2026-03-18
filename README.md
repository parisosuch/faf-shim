# faf-shim

A lightweight, self-hostable webhook shim. Point any service at faf-shim, define routing rules, transform payloads, and forward to the right destination — no code required.

**Stack:** FastAPI · SQLite (WAL mode, async via aiosqlite) · Astro (UI, coming soon)

---

## Concepts

### Shim
A shim is a named inbound endpoint identified by a user-configured **slug**. External services POST their webhooks to `/in/{slug}`. Each shim has a `target_url` that acts as the fallback destination if no rules match.

### Shim Rules
Rules are conditions attached to a shim that inspect the incoming request body and route to a specific `target_url` when matched. Rules are evaluated in `order` (ascending) — first match wins, fallback to the shim's `target_url` if none match.

Each rule defines:
- `field` — dot-separated path into the JSON body (e.g. `status`, `deployment.state`)
- `operator` — `==`, `!=`, or `contains`
- `value` — the value to compare against
- `target_url` — where to forward if the rule matches
- `body_template` *(optional)* — Jinja2 template for the outgoing body when this rule fires

**Example:** A Coolify shim with two rules:
```
POST /in/coolify-deploy
  Rule 1: status == "failed"  → https://pagerduty.example.com/...
  Rule 2: status == "success" → https://hooks.slack.com/...
  Fallback                    → https://logs.example.com/generic
```

### Body Templates
Each shim (and each rule) can define a **Jinja2 body template** that transforms the incoming payload into the shape expected by the target API. When a template is set on a matched rule it takes precedence over the shim-level template; when no template is configured the raw request body is forwarded unchanged.

Template context:
- `payload` — the parsed incoming JSON body
- `vars` — the shim's stored variables (see below)

**Example** — transform a Coolify deployment event into a Beaver notification:
```json
{
  "project": "Cove",
  "channel": "deployments",
  "title": "{{ payload.resource.name }} deployment {{ payload.status }}",
  "description": "{{ payload.message }}",
  "emoji": "🚀",
  "api_key": "{{ vars.BEAVER_API_KEY }}"
}
```

If the template references an undefined variable the forward is skipped, an error is written to the log, and the inbound caller still receives `200`.

### Variables
Variables are named key/value pairs stored per shim. They are available inside body templates and header templates via `{{ vars.KEY_NAME }}`. Use them to store API keys, static channel names, or any other configuration that shouldn't be hardcoded in a template.

Variables are returned as part of `GET /shims/{id}` and can be managed via the `/variables` sub-resource.

### Headers
The `headers` field on a shim is a JSON object of static HTTP headers sent with every forwarded request. Header values are also rendered as Jinja2 templates, so API keys can be injected from variables:

```json
{"Authorization": "Bearer {{ vars.TARGET_API_KEY }}"}
```

### Signature Verification
Each shim can optionally verify incoming request signatures to prevent unauthorized triggering. Two modes are supported:

- **`token`** — compares a header value directly against the stored secret (e.g. Coolify's `X-Coolify-Token`)
- **`sha256`** — verifies an HMAC-SHA256 signature of the request body (e.g. GitHub's `X-Hub-Signature-256`, Stripe's `Stripe-Signature`)

Configure per shim:
```json
{
  "secret": "your-shared-secret",
  "signature_header": "X-Hub-Signature-256",
  "signature_algorithm": "sha256"
}
```

If no secret is configured, the shim accepts all traffic. The `/in/{slug}` endpoint always returns `200` regardless of outcome — unknown slugs, missing headers, and invalid signatures are silently dropped with no distinguishable response to prevent enumeration.

### Sample Payload
The optional `sample_payload` field stores an example incoming payload for a shim. It has no effect on forwarding — it exists as a hint for UIs building template editors and autocomplete.

### Configuration
faf-shim stores application-wide settings in a `GET /config` / `PATCH /config` resource (auth required). These are persisted in the database and take effect immediately without a restart.

| Field | Default | Description |
|-------|---------|-------------|
| `cors_origins` | `["*"]` | List of allowed CORS origins. Use `["*"]` to allow all. |
| `log_retention_days` | `30` | How many days of webhook logs to keep. `0` = keep forever. |
| `max_body_size_kb` | `1024` | Global hard cap on inbound request body size in KB. Requests over this limit are silently dropped. |
| `cleanup_interval_seconds` | `3600` | How often the background cleanup task runs to delete expired logs. |

Per-shim overrides can be set when creating or updating a shim:

| Field | Description |
|-------|-------------|
| `max_body_size_kb` | Override the global body size limit for this shim (must be ≤ global to have any effect). |
| `log_retention_days` | Override log retention for this shim. `0` = keep forever. |
| `rate_limit_requests` | Max requests allowed per window. Requests over the limit receive `429`. |
| `rate_limit_window_seconds` | Fixed window size in seconds for rate limiting. |

---

## Authentication

faf-shim uses JWT bearer tokens. All `/shims/*` management endpoints require authentication. The `/in/{slug}` inbound endpoint and `/health` are public.

Credentials are configured via environment variables. See `.env.example` for setup instructions.

### Generating credentials

```bash
# Hash a password
uv run python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"

# Generate a JWT secret
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

---

## API Reference

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login` | Login with username + password, returns JWT |
| `GET` | `/auth/me` | Check current session, returns username |
| `POST` | `/auth/refresh` | Issue a new token from a valid token |

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/in/{slug}` | Receive an inbound webhook (public) |

### Shims

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/shims/` | List all shims (includes rules and variables) |
| `POST` | `/shims/` | Create a shim |
| `GET` | `/shims/{id}` | Get a shim with its rules and variables |
| `PATCH` | `/shims/{id}` | Update a shim |
| `DELETE` | `/shims/{id}` | Delete a shim, its rules, and its variables |
| `GET` | `/shims/{id}/rules` | List rules for a shim (ordered) |
| `POST` | `/shims/{id}/rules` | Add a rule to a shim |
| `PATCH` | `/shims/{id}/rules/{rule_id}` | Update a rule |
| `DELETE` | `/shims/{id}/rules/{rule_id}` | Delete a rule |
| `GET` | `/shims/{id}/variables` | List variables for a shim |
| `POST` | `/shims/{id}/variables` | Add a variable to a shim |
| `PATCH` | `/shims/{id}/variables/{var_id}` | Update a variable |
| `DELETE` | `/shims/{id}/variables/{var_id}` | Delete a variable |
| `POST` | `/shims/{id}/test` | Dry-run: evaluate rules and render templates against a sample payload |
| `GET` | `/shims/{id}/logs` | Retrieve webhook logs (paginated) |
| `GET` | `/shims/{id}/logs/{log_id}` | Get a single log entry |
| `GET` | `/shims/operators` | List valid rule operators |

### Metrics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/metrics/` | Aggregate stats and time-series buckets per shim and globally |

**Query parameters:**

| Param | Values | Default | Description |
|-------|--------|---------|-------------|
| `bucket` | `hour` \| `day` \| `week` \| `month` | `day` | Time bucket size |
| `range` | integer ≥ 1 | `30` | Number of buckets to return |

**Response shape:**
```json
{
  "global": {
    "total_requests": 1234, "successful_forwards": 1100, "failed_forwards": 134,
    "avg_duration_ms": 245.3, "cache_hits": 890, "cache_misses": 344,
    "buckets": [{"bucket": "2026-03-17", "requests": 45, "successful_forwards": 40, "failed_forwards": 5, "avg_duration_ms": 210.5}]
  },
  "shims": [
    {"shim_id": 1, "slug": "coolify", "name": "Coolify", "total_requests": 500,
     "successful_forwards": 480, "failed_forwards": 20, "avg_duration_ms": 180.2,
     "last_triggered_at": "2026-03-17T12:00:00", "buckets": [...]}
  ]
}
```

Aggregate totals are derived from persisted `webhook_log` rows — no extra writes on the hot path. Cache hit/miss counters are in-memory and reset on restart.

### Config

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/config/` | Get current application configuration |
| `PATCH` | `/config/` | Update application configuration (partial updates supported) |

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |

Interactive API docs available at `/docs` when running locally.

### Test dry-run response

`POST /shims/{id}/test` accepts `{"payload": {...}}` and returns:

```json
{
  "matched_rule": { ... } | null,
  "target_url": "https://...",
  "rendered_body": "{ \"title\": \"...\" }" | null,
  "rendered_headers": { "Authorization": "Bearer ..." } | null
}
```

`rendered_body` and `rendered_headers` are `null` when no template / non-default headers are configured. On template error, `rendered_body` contains the error message string.

---

## Development

### Requirements
- Python 3.11+
- [uv](https://github.com/astral-sh/uv)

### Setup

```bash
cp .env.example .env
# Fill in ADMIN_PASSWORD_HASH and JWT_SECRET in .env
uv sync
uv run fastapi dev app/main.py
```

The SQLite database (`faf-shim.db`) is created automatically on first run with WAL mode enabled.

### Testing

Tests use an in-memory SQLite database — nothing touches the real `faf-shim.db`.

```bash
uv run pytest tests/ -v
```

---

## Project Structure

```
app/
├── main.py              # FastAPI app, lifespan, CORS middleware, router registration
├── app_config.py        # In-memory singleton for AppConfig (avoids DB hit on hot paths)
├── cleanup.py           # Background task that deletes expired webhook logs
├── rate_limit.py        # In-memory fixed-window rate limiter, keyed by shim slug
├── auth.py              # JWT creation/validation, bcrypt password hashing
├── cache.py             # In-memory slug→(shim, rules, variables) cache
├── config.py            # Settings loaded from environment via pydantic-settings
├── forwarder.py         # Rule evaluation, template rendering, HTTP forwarding
├── signing.py           # Webhook signature verification (token + HMAC-SHA256)
├── db/
│   ├── __init__.py      # Package exports
│   ├── engine.py        # Async SQLite engine, session dependency, DB init
│   └── models.py        # SQLModel table definitions and request/response schemas
└── routers/
    ├── auth.py          # Login, session check, token refresh
    ├── config.py        # GET/PATCH /config — application-wide settings
    ├── metrics.py       # GET /metrics/ — aggregate stats and time-series buckets
    ├── shims.py         # Shim, ShimRule, ShimVariable CRUD + test dry-run + logs
    └── webhooks.py      # Inbound webhook receiver (background forwarding)
tests/
├── conftest.py          # In-memory async DB fixture, TestClient + auth setup
├── test_auth.py         # Login, session, refresh, protection tests
├── test_body_size.py    # Global and per-shim body size limit enforcement tests
├── test_cleanup.py      # Log cleanup task tests
├── test_config.py       # GET/PATCH /config endpoint tests
├── test_cors.py         # Dynamic CORS middleware tests
├── test_forwarder.py    # Rule evaluation, find_matching_rule, render_template unit tests
├── test_log_retention.py # Global and per-shim log retention tests
├── test_logs.py         # Webhook log retrieval and pagination tests
├── test_rules.py        # ShimRule CRUD tests
├── test_shim_test.py    # Dry-run endpoint tests
├── test_shims.py        # Shim CRUD tests
├── test_templates.py    # Body/header template rendering integration tests
├── test_updates.py      # PATCH shim and rule tests
├── test_variables.py    # ShimVariable CRUD and cache invalidation tests
├── test_metrics.py      # Metrics endpoint and bucketing tests
├── test_rate_limit.py   # Rate limiting enforcement tests
└── test_webhooks.py     # Inbound webhook + signature verification tests
```
