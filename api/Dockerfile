FROM python:3.14-slim

WORKDIR /app

# Install uv (pinned for reproducible builds)
COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /usr/local/bin/uv

# Install dependencies — cached layer, only re-runs when lockfile changes
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Copy application code
COPY . .

# SQLite data lives in a volume at /data
RUN mkdir -p /data
ENV DATABASE_URL=sqlite+aiosqlite:////data/faf-shim.db

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
