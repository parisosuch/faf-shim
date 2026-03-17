from fastapi.testclient import TestClient


def test_login_success(client: TestClient):
    r = client.post("/auth/login", json={"username": "admin", "password": "testpassword"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient):
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_wrong_username(client: TestClient):
    r = client.post("/auth/login", json={"username": "notadmin", "password": "testpassword"})
    assert r.status_code == 401


def test_protected_route_no_token(client: TestClient):
    r = client.get("/shims/")
    assert r.status_code == 401


def test_protected_route_invalid_token(client: TestClient):
    r = client.get("/shims/", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_me(client: TestClient, auth_headers):
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_me_unauthenticated(client: TestClient):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_refresh(client: TestClient, auth_headers):
    import jwt as pyjwt
    original_token = auth_headers["Authorization"].split(" ")[1]

    r = client.post("/auth/refresh", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # refreshed token must have a later or equal expiry and a valid sub
    original = pyjwt.decode(original_token, options={"verify_signature": False})
    refreshed = pyjwt.decode(data["access_token"], options={"verify_signature": False})
    assert refreshed["sub"] == original["sub"]
    assert refreshed["exp"] >= original["exp"]


def test_refresh_unauthenticated(client: TestClient):
    r = client.post("/auth/refresh")
    assert r.status_code == 401
