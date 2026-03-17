import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def shim(client: TestClient, auth_headers):
    r = client.post("/shims/", headers=auth_headers, json={
        "name": "Rule Shim", "slug": "rule-shim", "target_url": "https://fallback.com"
    })
    return r.json()


def test_create_rule(client: TestClient, auth_headers, shim):
    r = client.post(f"/shims/{shim['id']}/rules", headers=auth_headers, json={
        "field": "status",
        "operator": "==",
        "value": "failed",
        "target_url": "https://pagerduty.com",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["field"] == "status"
    assert data["shim_id"] == shim["id"]


def test_create_rule_invalid_operator(client: TestClient, auth_headers, shim):
    r = client.post(f"/shims/{shim['id']}/rules", headers=auth_headers, json={
        "field": "status",
        "operator": ">=",
        "value": "failed",
        "target_url": "https://example.com",
    })
    assert r.status_code == 422


def test_create_rule_shim_not_found(client: TestClient, auth_headers):
    r = client.post("/shims/999/rules", headers=auth_headers, json={
        "field": "status", "operator": "==", "value": "ok", "target_url": "https://example.com"
    })
    assert r.status_code == 404


def test_list_rules_ordered(client: TestClient, auth_headers, shim):
    client.post(f"/shims/{shim['id']}/rules", headers=auth_headers, json={
        "field": "status", "operator": "==", "value": "failed",
        "target_url": "https://a.com", "order": 2,
    })
    client.post(f"/shims/{shim['id']}/rules", headers=auth_headers, json={
        "field": "status", "operator": "==", "value": "success",
        "target_url": "https://b.com", "order": 1,
    })
    r = client.get(f"/shims/{shim['id']}/rules", headers=auth_headers)
    assert r.status_code == 200
    orders = [rule["order"] for rule in r.json()]
    assert orders == sorted(orders)


def test_delete_rule(client: TestClient, auth_headers, shim):
    rule = client.post(f"/shims/{shim['id']}/rules", headers=auth_headers, json={
        "field": "status", "operator": "==", "value": "ok", "target_url": "https://a.com"
    }).json()
    r = client.delete(f"/shims/{shim['id']}/rules/{rule['id']}", headers=auth_headers)
    assert r.status_code == 204
    rules = client.get(f"/shims/{shim['id']}/rules", headers=auth_headers).json()
    assert all(r["id"] != rule["id"] for r in rules)


def test_delete_rule_wrong_shim(client: TestClient, auth_headers):
    shim_a = client.post("/shims/", headers=auth_headers, json={
        "name": "A", "slug": "shim-a", "target_url": "https://a.com"
    }).json()
    shim_b = client.post("/shims/", headers=auth_headers, json={
        "name": "B", "slug": "shim-b", "target_url": "https://b.com"
    }).json()
    rule = client.post(f"/shims/{shim_a['id']}/rules", headers=auth_headers, json={
        "field": "x", "operator": "==", "value": "y", "target_url": "https://x.com"
    }).json()
    r = client.delete(f"/shims/{shim_b['id']}/rules/{rule['id']}", headers=auth_headers)
    assert r.status_code == 404
