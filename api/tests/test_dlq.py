from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def shim(client: TestClient, auth_headers):
    return client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "DLQ Shim", "slug": "dlq-shim", "target_url": "https://t.com"},
    ).json()


def _trigger(client: TestClient, status: int = 200, error: str | None = None):
    return_value = (status, error)
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = return_value
        client.post("/in/dlq-shim", json={"event": "push"})


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_list_dlq_requires_auth(client: TestClient):
    r = client.get("/dlq/")
    assert r.status_code == 401


def test_list_shim_dlq_requires_auth(client: TestClient, shim):
    r = client.get(f"/dlq/{shim['id']}")
    assert r.status_code == 401


def test_replay_requires_auth(client: TestClient):
    r = client.post("/dlq/1/replay")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# DLQ creation
# ---------------------------------------------------------------------------


def test_non_2xx_creates_dlq_entry(client: TestClient, auth_headers, shim):
    _trigger(client, status=500)
    r = client.get(f"/dlq/{shim['id']}", headers=auth_headers)
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) == 1
    assert entries[0]["status"] == 500
    assert entries[0]["target_url"] == "https://t.com"
    assert entries[0]["replayed_at"] is None


def test_network_error_creates_dlq_entry(client: TestClient, auth_headers, shim):
    _trigger(client, status=None, error="connection refused")
    r = client.get(f"/dlq/{shim['id']}", headers=auth_headers)
    entries = r.json()
    assert len(entries) == 1
    assert entries[0]["error"] == "connection refused"
    assert entries[0]["status"] is None


def test_2xx_does_not_create_dlq_entry(client: TestClient, auth_headers, shim):
    _trigger(client, status=200)
    r = client.get(f"/dlq/{shim['id']}", headers=auth_headers)
    assert r.json() == []


def test_multiple_failures_all_enqueued(client: TestClient, auth_headers, shim):
    _trigger(client, status=502)
    _trigger(client, status=503)
    _trigger(client, status=404)
    r = client.get(f"/dlq/{shim['id']}", headers=auth_headers)
    assert len(r.json()) == 3


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def test_list_dlq_shim_not_found(client: TestClient, auth_headers):
    r = client.get("/dlq/999", headers=auth_headers)
    assert r.status_code == 404


def test_list_dlq_global_returns_all_shims(client: TestClient, auth_headers):
    shim_a = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "A", "slug": "dlq-a", "target_url": "https://t.com"},
    ).json()
    shim_b = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "B", "slug": "dlq-b", "target_url": "https://t.com"},
    ).json()
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (500, None)
        client.post("/in/dlq-a", json={})
        client.post("/in/dlq-b", json={})
    r = client.get("/dlq/", headers=auth_headers)
    shim_ids = {e["shim_id"] for e in r.json()}
    assert shim_a["id"] in shim_ids
    assert shim_b["id"] in shim_ids


def test_list_dlq_pagination(client: TestClient, auth_headers, shim):
    for _ in range(5):
        _trigger(client, status=500)
    r1 = client.get(f"/dlq/{shim['id']}?limit=2&offset=0", headers=auth_headers)
    r2 = client.get(f"/dlq/{shim['id']}?limit=2&offset=2", headers=auth_headers)
    assert len(r1.json()) == 2
    assert len(r2.json()) == 2
    ids1 = {e["id"] for e in r1.json()}
    ids2 = {e["id"] for e in r2.json()}
    assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def test_replay_successful(client: TestClient, auth_headers, shim):
    _trigger(client, status=500)
    entry = client.get(f"/dlq/{shim['id']}", headers=auth_headers).json()[0]

    with patch("app.routers.dlq.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post(f"/dlq/{entry['id']}/replay", headers=auth_headers)

    assert r.status_code == 200
    data = r.json()
    assert data["replay_status"] == 200
    assert data["replay_error"] is None
    assert data["replayed_at"] is not None


def test_replay_failed(client: TestClient, auth_headers, shim):
    _trigger(client, status=500)
    entry = client.get(f"/dlq/{shim['id']}", headers=auth_headers).json()[0]

    with patch("app.routers.dlq.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (None, "timeout")
        r = client.post(f"/dlq/{entry['id']}/replay", headers=auth_headers)

    assert r.status_code == 200
    data = r.json()
    assert data["replay_error"] == "timeout"
    assert data["replayed_at"] is not None


def test_replay_updates_in_place(client: TestClient, auth_headers, shim):
    """Replaying the same entry twice should update, not duplicate."""
    _trigger(client, status=500)
    entry = client.get(f"/dlq/{shim['id']}", headers=auth_headers).json()[0]

    with patch("app.routers.dlq.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post(f"/dlq/{entry['id']}/replay", headers=auth_headers)
        mock_fwd.return_value = (201, None)
        r = client.post(f"/dlq/{entry['id']}/replay", headers=auth_headers)

    assert r.json()["replay_status"] == 201
    # Still only one DLQ entry
    assert len(client.get(f"/dlq/{shim['id']}", headers=auth_headers).json()) == 1


def test_replay_not_found(client: TestClient, auth_headers):
    r = client.post("/dlq/999/replay", headers=auth_headers)
    assert r.status_code == 404


def test_dlq_entry_links_to_webhook_log(client: TestClient, auth_headers, shim):
    _trigger(client, status=500)
    entry = client.get(f"/dlq/{shim['id']}", headers=auth_headers).json()[0]
    log = client.get(
        f"/shims/{shim['id']}/logs/{entry['webhook_log_id']}", headers=auth_headers
    )
    assert log.status_code == 200
    assert log.json()["status"] == 500
