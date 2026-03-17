import hashlib
import hmac

from fastapi.testclient import TestClient


def test_receive_webhook(client: TestClient, auth_headers):
    client.post("/shims/", headers=auth_headers, json={
        "name": "Coolify", "slug": "coolify", "target_url": "https://example.com"
    })
    r = client.post("/in/coolify", json={"status": "success"})
    assert r.status_code == 200
    assert r.json()["received"] is True


def test_receive_webhook_unknown_slug_returns_200(client: TestClient):
    # Must not leak whether a slug exists
    r = client.post("/in/does-not-exist", json={"status": "ok"})
    assert r.status_code == 200
    assert r.json()["received"] is True


def test_token_signature_valid(client: TestClient, auth_headers):
    client.post("/shims/", headers=auth_headers, json={
        "name": "Token Shim", "slug": "token-shim", "target_url": "https://example.com",
        "secret": "mysecret", "signature_header": "X-My-Token", "signature_algorithm": "token",
    })
    r = client.post("/in/token-shim", headers={"X-My-Token": "mysecret"}, json={})
    assert r.status_code == 200
    assert r.json()["received"] is True


def test_token_signature_invalid(client: TestClient, auth_headers):
    client.post("/shims/", headers=auth_headers, json={
        "name": "Token Shim 2", "slug": "token-shim-2", "target_url": "https://example.com",
        "secret": "mysecret", "signature_header": "X-My-Token", "signature_algorithm": "token",
    })
    # Wrong token — still returns 200, no info leakage
    r = client.post("/in/token-shim-2", headers={"X-My-Token": "wrongsecret"}, json={})
    assert r.status_code == 200
    assert r.json()["received"] is True


def test_token_signature_missing_header(client: TestClient, auth_headers):
    client.post("/shims/", headers=auth_headers, json={
        "name": "Token Shim 3", "slug": "token-shim-3", "target_url": "https://example.com",
        "secret": "mysecret", "signature_header": "X-My-Token", "signature_algorithm": "token",
    })
    r = client.post("/in/token-shim-3", json={})
    assert r.status_code == 200
    assert r.json()["received"] is True


def test_hmac_signature_valid(client: TestClient, auth_headers):
    secret = "webhooksecret"
    body = b'{"event":"push"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    client.post("/shims/", headers=auth_headers, json={
        "name": "HMAC Shim", "slug": "hmac-shim", "target_url": "https://example.com",
        "secret": secret, "signature_header": "X-Hub-Signature-256",
        "signature_algorithm": "sha256",
    })
    r = client.post(
        "/in/hmac-shim",
        content=body,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["received"] is True


def test_hmac_signature_invalid(client: TestClient, auth_headers):
    client.post("/shims/", headers=auth_headers, json={
        "name": "HMAC Shim 2", "slug": "hmac-shim-2", "target_url": "https://example.com",
        "secret": "webhooksecret", "signature_header": "X-Hub-Signature-256",
        "signature_algorithm": "sha256",
    })
    r = client.post(
        "/in/hmac-shim-2",
        content=b'{"event":"push"}',
        headers={"X-Hub-Signature-256": "sha256=invalidsignature"},
    )
    assert r.status_code == 200
    assert r.json()["received"] is True
