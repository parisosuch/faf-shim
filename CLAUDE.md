# faf-shim

A self-hostable webhook routing and transformation proxy. Incoming webhooks hit `/in/{slug}`, get matched against rules (with Jinja2 template support), and are forwarded to target URLs. Features: DLQ with replay, metrics, signature verification, JWT auth, SQLite persistence.

## Architecture

- `api/` — FastAPI + SQLModel + SQLite (aiosqlite, WAL mode)
- `client/` — Astro + React + TailwindCSS + DaisyUI
- `docker-compose.yml` — production; `docker-compose.override.yml` — local dev ports

## Development

### API (Python 3.14+, uv)

```bash
cd api
cp .env.example .env      # set ADMIN_PASSWORD and JWT_SECRET
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

Migrations:
```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
```

### Client (Node 22+, bun)

```bash
cd client
cp .env.example .env      # set PUBLIC_API_URL if needed
bun install
bun run dev
```

### Docker Compose (full stack)

```bash
cp api/.env.example api/.env
docker compose up --build
```

## Commands

### API

```bash
cd api
make test        # run pytest
make lint        # uvx ruff check
make format      # uvx ruff format
make check       # lint + test
```

Always run `uvx ruff check` and `uvx ruff format` before committing API changes.

### Client

```bash
cd client
bun run lint          # oxlint
bun run format        # oxfmt
bun run format:check
bun run build
```

Use `bun` (not `npm`) for all client scripts.

## Key Files

| Path | Purpose |
|------|---------|
| `api/app/main.py` | FastAPI app setup, lifespan, middleware |
| `api/app/forwarder.py` | Rule evaluation, Jinja2 rendering, HTTP forwarding |
| `api/app/db/models.py` | SQLModel tables + Pydantic schemas |
| `api/app/routers/` | Route handlers by domain |
| `api/app/cache.py` | In-memory slug→(shim, rules, vars) cache |
| `client/src/lib/api.ts` | API client utilities |
| `client/src/lib/types.ts` | TypeScript types mirroring backend schemas |
| `client/src/components/` | React components |

## Git Workflow

- Always branch before committing — never commit directly to `main`
- Do not include issue numbers in commit messages
- Do not add `Co-Authored-By` lines to commits

## Testing

API tests use in-memory SQLite — no disk side effects. Run with `make test` from `api/`.

No automated client tests; frontend is verified manually.
