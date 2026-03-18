from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import app_config as _app_config
from app.db.models import WebhookLog, _now


@pytest.fixture(autouse=True)
def reset_app_config():
    yield
    _app_config.update(log_retention_days=30)


@pytest.fixture
def shim(client: TestClient, auth_headers):
    return client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Retention Shim",
            "slug": "retention-shim",
            "target_url": "https://t.com",
        },
    ).json()


def _post_webhook(client: TestClient):
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/retention-shim", json={"event": "push"})


async def _insert_old_log(session: AsyncSession, shim_id: int, days_ago: int) -> None:
    log = WebhookLog(
        shim_id=shim_id,
        received_at=_now() - timedelta(days=days_ago),
        payload="{}",
        target_url="https://t.com",
        status=200,
    )
    session.add(log)
    await session.commit()


def test_recent_logs_returned(client: TestClient, auth_headers, shim):
    _post_webhook(client)
    r = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.anyio
async def test_old_logs_filtered_by_global_retention(
    client: TestClient, auth_headers, shim, session: AsyncSession
):
    _app_config.update(log_retention_days=7)
    await _insert_old_log(session, shim["id"], days_ago=10)  # outside window
    _post_webhook(client)  # inside window

    r = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers)
    assert r.status_code == 200
    logs = r.json()
    assert len(logs) == 1


@pytest.mark.anyio
async def test_retention_zero_returns_all_logs(
    client: TestClient, auth_headers, shim, session: AsyncSession
):
    _app_config.update(log_retention_days=0)
    await _insert_old_log(session, shim["id"], days_ago=365)
    _post_webhook(client)

    r = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.anyio
async def test_per_shim_retention_overrides_global(
    client: TestClient, auth_headers, session: AsyncSession
):
    """Per-shim retention takes precedence over global."""
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Short Retention",
            "slug": "short-retention",
            "target_url": "https://t.com",
            "log_retention_days": 3,
        },
    ).json()
    assert shim["log_retention_days"] == 3

    _app_config.update(log_retention_days=30)
    await _insert_old_log(session, shim["id"], days_ago=5)  # outside shim window (3d)

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/short-retention", json={"event": "x"})

    r = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers)
    assert r.status_code == 200
    # Only the recent log (within 3-day window) should appear
    assert len(r.json()) == 1


@pytest.mark.anyio
async def test_per_shim_retention_zero_returns_all(
    client: TestClient, auth_headers, session: AsyncSession
):
    """Per-shim retention of 0 keeps all logs even if global retention is short."""
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "No Retention",
            "slug": "no-retention",
            "target_url": "https://t.com",
            "log_retention_days": 0,
        },
    ).json()

    _app_config.update(log_retention_days=7)
    await _insert_old_log(session, shim["id"], days_ago=30)

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/no-retention", json={"event": "x"})

    r = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers)
    assert len(r.json()) == 2
