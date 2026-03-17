from fastapi.testclient import TestClient


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_operators(client: TestClient):
    r = client.get("/shims/operators")
    assert r.status_code == 200
    values = [op["value"] for op in r.json()]
    assert "==" in values
    assert "!=" in values
    assert "contains" in values


def test_create_shim(client: TestClient):
    r = client.post("/shims/", json={
        "name": "Test Shim",
        "slug": "test-shim",
        "target_url": "https://example.com/target",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "test-shim"
    assert data["id"] is not None


def test_create_shim_duplicate_slug(client: TestClient):
    payload = {"name": "Shim", "slug": "my-shim", "target_url": "https://example.com"}
    client.post("/shims/", json=payload)
    r = client.post("/shims/", json=payload)
    assert r.status_code == 409


def test_list_shims(client: TestClient):
    client.post("/shims/", json={"name": "A", "slug": "a", "target_url": "https://a.com"})
    client.post("/shims/", json={"name": "B", "slug": "b", "target_url": "https://b.com"})
    r = client.get("/shims/")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_shim(client: TestClient):
    created = client.post("/shims/", json={
        "name": "Get Me", "slug": "get-me", "target_url": "https://example.com"
    }).json()
    r = client.get(f"/shims/{created['id']}")
    assert r.status_code == 200
    assert r.json()["slug"] == "get-me"


def test_get_shim_not_found(client: TestClient):
    r = client.get("/shims/999")
    assert r.status_code == 404


def test_delete_shim(client: TestClient):
    created = client.post("/shims/", json={
        "name": "Delete Me", "slug": "delete-me", "target_url": "https://example.com"
    }).json()
    r = client.delete(f"/shims/{created['id']}")
    assert r.status_code == 204
    assert client.get(f"/shims/{created['id']}").status_code == 404


def test_delete_shim_cascades_rules(client: TestClient):
    shim = client.post("/shims/", json={
        "name": "Cascade", "slug": "cascade", "target_url": "https://example.com"
    }).json()
    client.post(f"/shims/{shim['id']}/rules", json={
        "field": "status", "operator": "==", "value": "ok", "target_url": "https://a.com"
    })
    client.delete(f"/shims/{shim['id']}")
    # shim is gone so rules endpoint should 404
    r = client.get(f"/shims/{shim['id']}/rules")
    assert r.status_code == 404
