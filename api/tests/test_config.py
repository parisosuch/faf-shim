import pytest
from fastapi.testclient import TestClient

from app import app_config as _app_config


@pytest.fixture(autouse=True)
def reset_app_config():
    """Reset in-memory config singleton to defaults after each test."""
    yield
    _app_config.update(cors_origins=["*"], log_retention_days=30, max_body_size_kb=1024)


def test_get_config_defaults(client: TestClient, auth_headers):
    r = client.get("/config/", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["cors_origins"] == ["*"]
    assert data["log_retention_days"] == 30
    assert data["max_body_size_kb"] == 1024


def test_patch_config_cors_origins(client: TestClient, auth_headers):
    r = client.patch(
        "/config/",
        headers=auth_headers,
        json={"cors_origins": ["https://example.com", "https://other.com"]},
    )
    assert r.status_code == 200
    assert r.json()["cors_origins"] == ["https://example.com", "https://other.com"]
    # In-memory singleton updated
    assert _app_config.get().cors_origins == [
        "https://example.com",
        "https://other.com",
    ]


def test_patch_config_retention(client: TestClient, auth_headers):
    r = client.patch("/config/", headers=auth_headers, json={"log_retention_days": 7})
    assert r.status_code == 200
    assert r.json()["log_retention_days"] == 7
    assert _app_config.get().log_retention_days == 7


def test_patch_config_body_size(client: TestClient, auth_headers):
    r = client.patch("/config/", headers=auth_headers, json={"max_body_size_kb": 512})
    assert r.status_code == 200
    assert r.json()["max_body_size_kb"] == 512
    assert _app_config.get().max_body_size_kb == 512


def test_patch_config_partial_update(client: TestClient, auth_headers):
    """Omitted fields must not be reset to defaults."""
    client.patch("/config/", headers=auth_headers, json={"log_retention_days": 14})
    r = client.patch("/config/", headers=auth_headers, json={"max_body_size_kb": 256})
    assert r.status_code == 200
    data = r.json()
    assert data["log_retention_days"] == 14
    assert data["max_body_size_kb"] == 256


def test_patch_config_retention_zero(client: TestClient, auth_headers):
    """Zero means keep logs forever."""
    r = client.patch("/config/", headers=auth_headers, json={"log_retention_days": 0})
    assert r.status_code == 200
    assert r.json()["log_retention_days"] == 0


def test_get_config_requires_auth(client: TestClient):
    r = client.get("/config/")
    assert r.status_code == 401


def test_patch_config_requires_auth(client: TestClient):
    r = client.patch("/config/", json={"log_retention_days": 7})
    assert r.status_code == 401
