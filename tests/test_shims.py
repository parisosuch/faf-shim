from fastapi.testclient import TestClient


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_operators(client: TestClient, auth_headers):
    r = client.get("/shims/operators", headers=auth_headers)
    assert r.status_code == 200
    values = [op["value"] for op in r.json()]
    assert "==" in values
    assert "!=" in values
    assert "contains" in values


def test_unauthenticated_request(client: TestClient):
    r = client.get("/shims/")
    assert r.status_code == 401


def test_create_shim(client: TestClient, auth_headers):
    r = client.post("/shims/", headers=auth_headers, json={
        "name": "Test Shim",
        "slug": "test-shim",
        "target_url": "https://example.com/target",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "test-shim"
    assert data["id"] is not None


def test_create_shim_duplicate_slug(client: TestClient, auth_headers):
    payload = {"name": "Shim", "slug": "my-shim", "target_url": "https://example.com"}
    client.post("/shims/", headers=auth_headers, json=payload)
    r = client.post("/shims/", headers=auth_headers, json=payload)
    assert r.status_code == 409


def test_list_shims(client: TestClient, auth_headers):
    client.post("/shims/", headers=auth_headers, json={"name": "A", "slug": "a", "target_url": "https://a.com"})
    client.post("/shims/", headers=auth_headers, json={"name": "B", "slug": "b", "target_url": "https://b.com"})
    r = client.get("/shims/", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_shim(client: TestClient, auth_headers):
    created = client.post("/shims/", headers=auth_headers, json={
        "name": "Get Me", "slug": "get-me", "target_url": "https://example.com"
    }).json()
    r = client.get(f"/shims/{created['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["slug"] == "get-me"


def test_get_shim_not_found(client: TestClient, auth_headers):
    r = client.get("/shims/999", headers=auth_headers)
    assert r.status_code == 404


def test_delete_shim(client: TestClient, auth_headers):
    created = client.post("/shims/", headers=auth_headers, json={
        "name": "Delete Me", "slug": "delete-me", "target_url": "https://example.com"
    }).json()
    r = client.delete(f"/shims/{created['id']}", headers=auth_headers)
    assert r.status_code == 204
    assert client.get(f"/shims/{created['id']}", headers=auth_headers).status_code == 404


def test_delete_shim_cascades_rules(client: TestClient, auth_headers):
    shim = client.post("/shims/", headers=auth_headers, json={
        "name": "Cascade", "slug": "cascade", "target_url": "https://example.com"
    }).json()
    client.post(f"/shims/{shim['id']}/rules", headers=auth_headers, json={
        "field": "status", "operator": "==", "value": "ok", "target_url": "https://a.com"
    })
    client.delete(f"/shims/{shim['id']}", headers=auth_headers)
    r = client.get(f"/shims/{shim['id']}/rules", headers=auth_headers)
    assert r.status_code == 404
