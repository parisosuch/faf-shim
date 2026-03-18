import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def shim(client: TestClient, auth_headers):
    s = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Test Shim",
            "slug": "test-me",
            "target_url": "https://fallback.com",
        },
    ).json()
    client.post(
        f"/shims/{s['id']}/rules",
        headers=auth_headers,
        json={
            "field": "status",
            "operator": "==",
            "value": "failed",
            "target_url": "https://pagerduty.com",
            "order": 0,
        },
    )
    client.post(
        f"/shims/{s['id']}/rules",
        headers=auth_headers,
        json={
            "field": "status",
            "operator": "==",
            "value": "success",
            "target_url": "https://slack.com",
            "order": 1,
        },
    )
    return s


def test_test_matches_rule(client: TestClient, auth_headers, shim):
    r = client.post(
        f"/shims/{shim['id']}/test",
        headers=auth_headers,
        json={"payload": {"status": "failed"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["target_url"] == "https://pagerduty.com"
    assert data["matched_rule"]["value"] == "failed"


def test_test_falls_back_when_no_match(client: TestClient, auth_headers, shim):
    r = client.post(
        f"/shims/{shim['id']}/test",
        headers=auth_headers,
        json={"payload": {"status": "unknown"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["target_url"] == "https://fallback.com"
    assert data["matched_rule"] is None


def test_test_nested_field(client: TestClient, auth_headers):
    s = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Nested", "slug": "nested", "target_url": "https://fallback.com"},
    ).json()
    client.post(
        f"/shims/{s['id']}/rules",
        headers=auth_headers,
        json={
            "field": "deployment.state",
            "operator": "==",
            "value": "error",
            "target_url": "https://alerts.com",
            "order": 0,
        },
    )
    r = client.post(
        f"/shims/{s['id']}/test",
        headers=auth_headers,
        json={"payload": {"deployment": {"state": "error"}}},
    )
    assert r.status_code == 200
    assert r.json()["target_url"] == "https://alerts.com"


def test_test_shim_not_found(client: TestClient, auth_headers):
    r = client.post(
        "/shims/999/test",
        headers=auth_headers,
        json={"payload": {"status": "ok"}},
    )
    assert r.status_code == 404
