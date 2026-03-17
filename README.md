# faf-shim

A lightweight, self-hostable webhook shim. Point any service at faf-shim, define routing rules, and forward payloads to the right destination — no code required.

**Stack:** FastAPI · SQLite (WAL mode) · Astro (UI, coming soon)

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

**Example:** A Coolify shim with two rules:
```
POST /in/coolify-deploy
  Rule 1: status == "failed"  → https://pagerduty.example.com/...
  Rule 2: status == "success" → https://hooks.slack.com/...
  Fallback                    → https://logs.example.com/generic
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
| `GET` | `/shims/` | List all shims |
| `POST` | `/shims/` | Create a shim |
| `GET` | `/shims/{id}` | Get a shim |
| `DELETE` | `/shims/{id}` | Delete a shim and its rules |
| `GET` | `/shims/{id}/rules` | List rules for a shim (ordered) |
| `POST` | `/shims/{id}/rules` | Add a rule to a shim |
| `DELETE` | `/shims/{id}/rules/{rule_id}` | Delete a rule |
| `GET` | `/shims/operators` | List valid rule operators |

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |

Interactive API docs available at `/docs` when running locally.

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
├── main.py              # FastAPI app, lifespan, router registration
├── auth.py              # JWT creation/validation, bcrypt password hashing
├── config.py            # Settings loaded from environment via pydantic-settings
├── signing.py           # Webhook signature verification (token + HMAC-SHA256)
├── db/
│   ├── __init__.py      # Package exports
│   ├── engine.py        # SQLite engine, session dependency, DB init
│   └── models.py        # SQLModel table definitions and request schemas
└── routers/
    ├── auth.py          # Login, session check, token refresh
    ├── shims.py         # Shim + ShimRule CRUD endpoints
    └── webhooks.py      # Inbound webhook receiver
tests/
├── conftest.py          # In-memory DB fixture, TestClient + auth setup
├── test_auth.py         # Login, session, refresh, protection tests
├── test_shims.py        # Shim CRUD tests
├── test_rules.py        # ShimRule CRUD tests
└── test_webhooks.py     # Inbound webhook + signature verification tests
```
