from fastapi.testclient import TestClient


def test_receive_webhook(client: TestClient):
    client.post("/shims/", json={
        "name": "Coolify", "slug": "coolify", "target_url": "https://example.com"
    })
    r = client.post("/in/coolify", json={"status": "success"})
    assert r.status_code == 200
    assert r.json()["received"] is True


def test_receive_webhook_unknown_slug(client: TestClient):
    r = client.post("/in/does-not-exist", json={"status": "ok"})
    assert r.status_code == 404
