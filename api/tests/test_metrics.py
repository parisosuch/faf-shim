from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models import WebhookLog
from app.utils import now


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def shim(client: TestClient, auth_headers):
    return client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Metrics Shim", "slug": "m-shim", "target_url": "https://t.com"},
    ).json()


def _trigger(client: TestClient, slug: str = "m-shim", times: int = 1):
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        for _ in range(times):
            client.post(f"/in/{slug}", json={"event": "push"})


async def _insert_log(
    session: AsyncSession,
    shim_id: int,
    *,
    days_ago: int = 0,
    status: int = 200,
    duration_ms: int = 100,
    error: str | None = None,
) -> None:
    log = WebhookLog(
        shim_id=shim_id,
        received_at=now() - timedelta(days=days_ago),
        payload="{}",
        target_url="https://t.com",
        status=status,
        duration_ms=duration_ms,
        error=error,
    )
    session.add(log)
    await session.commit()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_metrics_requires_auth(client: TestClient):
    r = client.get("/metrics/")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


def test_metrics_returns_global_and_shims(client: TestClient, auth_headers, shim):
    r = client.get("/metrics/", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "global" in data
    assert "shims" in data


def test_metrics_global_fields_present(client: TestClient, auth_headers, shim):
    r = client.get("/metrics/", headers=auth_headers)
    g = r.json()["global"]
    for field in (
        "total_requests",
        "successful_forwards",
        "failed_forwards",
        "avg_duration_ms",
        "cache_hits",
        "cache_misses",
        "buckets",
    ):
        assert field in g


def test_metrics_shim_fields_present(client: TestClient, auth_headers, shim):
    r = client.get("/metrics/", headers=auth_headers)
    s = r.json()["shims"][0]
    for field in (
        "shim_id",
        "slug",
        "name",
        "total_requests",
        "successful_forwards",
        "failed_forwards",
        "avg_duration_ms",
        "last_triggered_at",
        "buckets",
    ):
        assert field in s


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_total_requests_counts_all_logs(
    client: TestClient, auth_headers, shim, session: AsyncSession
):
    await _insert_log(session, shim["id"])
    await _insert_log(session, shim["id"])
    await _insert_log(session, shim["id"])
    r = client.get("/metrics/", headers=auth_headers)
    s = next(x for x in r.json()["shims"] if x["shim_id"] == shim["id"])
    assert s["total_requests"] == 3


@pytest.mark.anyio
async def test_successful_forwards_counts_2xx(
    client: TestClient, auth_headers, shim, session: AsyncSession
):
    await _insert_log(session, shim["id"], status=200)
    await _insert_log(session, shim["id"], status=201)
    await _insert_log(session, shim["id"], status=500)
    await _insert_log(session, shim["id"], error="timeout", status=None, duration_ms=0)
    r = client.get("/metrics/", headers=auth_headers)
    s = next(x for x in r.json()["shims"] if x["shim_id"] == shim["id"])
    assert s["successful_forwards"] == 2
    assert s["failed_forwards"] == 1  # only the error one


@pytest.mark.anyio
async def test_avg_duration_ms(
    client: TestClient, auth_headers, shim, session: AsyncSession
):
    await _insert_log(session, shim["id"], duration_ms=100)
    await _insert_log(session, shim["id"], duration_ms=200)
    r = client.get("/metrics/", headers=auth_headers)
    s = next(x for x in r.json()["shims"] if x["shim_id"] == shim["id"])
    assert s["avg_duration_ms"] == 150.0


@pytest.mark.anyio
async def test_global_totals_sum_across_shims(
    client: TestClient, auth_headers, session: AsyncSession
):
    shim_a = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "A", "slug": "ma", "target_url": "https://t.com"},
    ).json()
    shim_b = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "B", "slug": "mb", "target_url": "https://t.com"},
    ).json()
    await _insert_log(session, shim_a["id"])
    await _insert_log(session, shim_a["id"])
    await _insert_log(session, shim_b["id"])
    r = client.get("/metrics/", headers=auth_headers)
    assert r.json()["global"]["total_requests"] == 3


# ---------------------------------------------------------------------------
# Cache stats
# ---------------------------------------------------------------------------


def test_cache_hits_and_misses(client: TestClient, auth_headers, shim):
    # First hit is a miss (not cached), subsequent are hits
    _trigger(client, slug="m-shim", times=3)
    r = client.get("/metrics/", headers=auth_headers)
    g = r.json()["global"]
    assert g["cache_misses"] >= 1
    assert g["cache_hits"] >= 2


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_buckets_respect_range(
    client: TestClient, auth_headers, shim, session: AsyncSession
):
    """Logs outside the range window should not appear in buckets."""
    await _insert_log(session, shim["id"], days_ago=0)  # inside range=7
    await _insert_log(session, shim["id"], days_ago=10)  # outside range=7

    r = client.get("/metrics/?bucket=day&range=7", headers=auth_headers)
    s = next(x for x in r.json()["shims"] if x["shim_id"] == shim["id"])
    total_in_buckets = sum(b["requests"] for b in s["buckets"])
    assert total_in_buckets == 1


@pytest.mark.anyio
async def test_bucket_keys_match_bucket_size(
    client: TestClient, auth_headers, shim, session: AsyncSession
):
    await _insert_log(session, shim["id"])
    r = client.get("/metrics/?bucket=day&range=1", headers=auth_headers)
    s = next(x for x in r.json()["shims"] if x["shim_id"] == shim["id"])
    if s["buckets"]:
        # Day bucket format: YYYY-MM-DD
        assert len(s["buckets"][0]["bucket"]) == 10

    r = client.get("/metrics/?bucket=month&range=1", headers=auth_headers)
    s = next(x for x in r.json()["shims"] if x["shim_id"] == shim["id"])
    if s["buckets"]:
        # Month bucket format: YYYY-MM
        assert len(s["buckets"][0]["bucket"]) == 7


@pytest.mark.anyio
async def test_global_buckets_aggregate_all_shims(
    client: TestClient, auth_headers, session: AsyncSession
):
    shim_a = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "GA", "slug": "ga", "target_url": "https://t.com"},
    ).json()
    shim_b = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "GB", "slug": "gb", "target_url": "https://t.com"},
    ).json()
    await _insert_log(session, shim_a["id"])
    await _insert_log(session, shim_b["id"])

    r = client.get("/metrics/?bucket=day&range=1", headers=auth_headers)
    global_buckets = r.json()["global"]["buckets"]
    total = sum(b["requests"] for b in global_buckets)
    assert total == 2


@pytest.mark.anyio
async def test_shim_with_no_logs_returns_zero_counts(client: TestClient, auth_headers):
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Empty", "slug": "empty-m", "target_url": "https://t.com"},
    ).json()
    r = client.get("/metrics/", headers=auth_headers)
    s = next(x for x in r.json()["shims"] if x["shim_id"] == shim["id"])
    assert s["total_requests"] == 0
    assert s["buckets"] == []
