from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def shim(client: TestClient, auth_headers):
    return client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Log Shim",
            "slug": "log-shim",
            "target_url": "https://target.com",
        },
    ).json()


def _trigger(client, times=1):
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        for _ in range(times):
            client.post("/in/log-shim", json={"event": "push"})


def test_list_logs(client: TestClient, auth_headers, shim):
    _trigger(client, times=3)
    r = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_list_logs_most_recent_first(client: TestClient, auth_headers, shim):
    _trigger(client, times=3)
    r = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers)
    logs = r.json()
    dates = [log["received_at"] for log in logs]
    assert dates == sorted(dates, reverse=True)


def test_list_logs_pagination(client: TestClient, auth_headers, shim):
    _trigger(client, times=5)
    r = client.get(f"/shims/{shim['id']}/logs?limit=2&offset=0", headers=auth_headers)
    assert len(r.json()) == 2
    r2 = client.get(f"/shims/{shim['id']}/logs?limit=2&offset=2", headers=auth_headers)
    assert len(r2.json()) == 2
    # no overlap
    ids_page1 = {log["id"] for log in r.json()}
    ids_page2 = {log["id"] for log in r2.json()}
    assert ids_page1.isdisjoint(ids_page2)


def test_list_logs_shim_not_found(client: TestClient, auth_headers):
    r = client.get("/shims/999/logs", headers=auth_headers)
    assert r.status_code == 404


def test_get_log(client: TestClient, auth_headers, shim):
    _trigger(client)
    logs = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers).json()
    log_id = logs[0]["id"]
    r = client.get(f"/shims/{shim['id']}/logs/{log_id}", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == log_id
    assert data["target_url"] == "https://target.com"
    assert data["status"] == 200


def test_get_log_not_found(client: TestClient, auth_headers, shim):
    r = client.get(f"/shims/{shim['id']}/logs/999", headers=auth_headers)
    assert r.status_code == 404


def test_get_log_wrong_shim(client: TestClient, auth_headers, shim):
    other = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Other", "slug": "other-shim", "target_url": "https://other.com"},
    ).json()
    _trigger(client)
    logs = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers).json()
    log_id = logs[0]["id"]
    # try to access log via wrong shim
    r = client.get(f"/shims/{other['id']}/logs/{log_id}", headers=auth_headers)
    assert r.status_code == 404
