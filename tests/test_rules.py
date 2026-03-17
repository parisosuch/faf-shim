import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def shim(client: TestClient):
    r = client.post("/shims/", json={
        "name": "Rule Shim", "slug": "rule-shim", "target_url": "https://fallback.com"
    })
    return r.json()


def test_create_rule(client: TestClient, shim):
    r = client.post(f"/shims/{shim['id']}/rules", json={
        "field": "status",
        "operator": "==",
        "value": "failed",
        "target_url": "https://pagerduty.com",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["field"] == "status"
    assert data["shim_id"] == shim["id"]


def test_create_rule_invalid_operator(client: TestClient, shim):
    r = client.post(f"/shims/{shim['id']}/rules", json={
        "field": "status",
        "operator": ">=",
        "value": "failed",
        "target_url": "https://example.com",
    })
    assert r.status_code == 422


def test_create_rule_shim_not_found(client: TestClient):
    r = client.post("/shims/999/rules", json={
        "field": "status", "operator": "==", "value": "ok", "target_url": "https://example.com"
    })
    assert r.status_code == 404


def test_list_rules_ordered(client: TestClient, shim):
    client.post(f"/shims/{shim['id']}/rules", json={
        "field": "status", "operator": "==", "value": "failed",
        "target_url": "https://a.com", "order": 2,
    })
    client.post(f"/shims/{shim['id']}/rules", json={
        "field": "status", "operator": "==", "value": "success",
        "target_url": "https://b.com", "order": 1,
    })
    r = client.get(f"/shims/{shim['id']}/rules")
    assert r.status_code == 200
    orders = [rule["order"] for rule in r.json()]
    assert orders == sorted(orders)


def test_delete_rule(client: TestClient, shim):
    rule = client.post(f"/shims/{shim['id']}/rules", json={
        "field": "status", "operator": "==", "value": "ok", "target_url": "https://a.com"
    }).json()
    r = client.delete(f"/shims/{shim['id']}/rules/{rule['id']}")
    assert r.status_code == 204
    rules = client.get(f"/shims/{shim['id']}/rules").json()
    assert all(rule["id"] != rule["id"] for rule in rules)


def test_delete_rule_wrong_shim(client: TestClient, client_fixture=None):
    shim_a = client.post("/shims/", json={
        "name": "A", "slug": "shim-a", "target_url": "https://a.com"
    }).json()
    shim_b = client.post("/shims/", json={
        "name": "B", "slug": "shim-b", "target_url": "https://b.com"
    }).json()
    rule = client.post(f"/shims/{shim_a['id']}/rules", json={
        "field": "x", "operator": "==", "value": "y", "target_url": "https://x.com"
    }).json()
    # try to delete shim_a's rule via shim_b's endpoint
    r = client.delete(f"/shims/{shim_b['id']}/rules/{rule['id']}")
    assert r.status_code == 404
