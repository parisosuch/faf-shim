import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def shim(client: TestClient, auth_headers):
    return client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Original",
            "slug": "original",
            "target_url": "https://original.com",
        },
    ).json()


@pytest.fixture
def rule(client: TestClient, auth_headers, shim):
    return client.post(
        f"/shims/{shim['id']}/rules",
        headers=auth_headers,
        json={
            "field": "status",
            "operator": "==",
            "value": "failed",
            "target_url": "https://alerts.com",
            "order": 0,
        },
    ).json()


# --- Shim update tests ---


def test_update_shim_name(client: TestClient, auth_headers, shim):
    r = client.patch(
        f"/shims/{shim['id']}", headers=auth_headers, json={"name": "Updated"}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Updated"
    assert r.json()["slug"] == "original"  # unchanged


def test_update_shim_slug(client: TestClient, auth_headers, shim):
    r = client.patch(
        f"/shims/{shim['id']}", headers=auth_headers, json={"slug": "new-slug"}
    )
    assert r.status_code == 200
    assert r.json()["slug"] == "new-slug"


def test_update_shim_duplicate_slug(client: TestClient, auth_headers, shim):
    client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Other", "slug": "taken", "target_url": "https://other.com"},
    )
    r = client.patch(
        f"/shims/{shim['id']}", headers=auth_headers, json={"slug": "taken"}
    )
    assert r.status_code == 409


def test_update_shim_same_slug_is_allowed(client: TestClient, auth_headers, shim):
    r = client.patch(
        f"/shims/{shim['id']}", headers=auth_headers, json={"slug": "original"}
    )
    assert r.status_code == 200


def test_update_shim_partial(client: TestClient, auth_headers, shim):
    r = client.patch(
        f"/shims/{shim['id']}",
        headers=auth_headers,
        json={"target_url": "https://new-target.com"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["target_url"] == "https://new-target.com"
    assert data["name"] == "Original"  # unchanged


def test_update_shim_returns_rules(client: TestClient, auth_headers, shim, rule):
    r = client.patch(
        f"/shims/{shim['id']}", headers=auth_headers, json={"name": "With Rules"}
    )
    assert r.status_code == 200
    assert len(r.json()["rules"]) == 1


def test_update_shim_not_found(client: TestClient, auth_headers):
    r = client.patch("/shims/999", headers=auth_headers, json={"name": "Ghost"})
    assert r.status_code == 404


# --- Rule update tests ---


def test_update_rule_value(client: TestClient, auth_headers, shim, rule):
    r = client.patch(
        f"/shims/{shim['id']}/rules/{rule['id']}",
        headers=auth_headers,
        json={"value": "success"},
    )
    assert r.status_code == 200
    assert r.json()["value"] == "success"
    assert r.json()["field"] == "status"  # unchanged


def test_update_rule_operator(client: TestClient, auth_headers, shim, rule):
    r = client.patch(
        f"/shims/{shim['id']}/rules/{rule['id']}",
        headers=auth_headers,
        json={"operator": "!="},
    )
    assert r.status_code == 200
    assert r.json()["operator"] == "!="


def test_update_rule_invalid_operator(client: TestClient, auth_headers, shim, rule):
    r = client.patch(
        f"/shims/{shim['id']}/rules/{rule['id']}",
        headers=auth_headers,
        json={"operator": ">="},
    )
    assert r.status_code == 422


def test_update_rule_order(client: TestClient, auth_headers, shim, rule):
    r = client.patch(
        f"/shims/{shim['id']}/rules/{rule['id']}",
        headers=auth_headers,
        json={"order": 5},
    )
    assert r.status_code == 200
    assert r.json()["order"] == 5


def test_update_rule_not_found(client: TestClient, auth_headers, shim):
    r = client.patch(
        f"/shims/{shim['id']}/rules/999", headers=auth_headers, json={"value": "x"}
    )
    assert r.status_code == 404


def test_update_rule_wrong_shim(client: TestClient, auth_headers, shim, rule):
    other = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Other", "slug": "other", "target_url": "https://other.com"},
    ).json()
    r = client.patch(
        f"/shims/{other['id']}/rules/{rule['id']}",
        headers=auth_headers,
        json={"value": "x"},
    )
    assert r.status_code == 404
