import pytest
from fastapi.testclient import TestClient

from app import app_config as _app_config


@pytest.fixture(autouse=True)
def reset_app_config():
    yield
    _app_config.update(cors_origins=["*"])


def test_wildcard_allows_any_origin(client: TestClient):
    _app_config.update(cors_origins=["*"])
    r = client.get("/health", headers={"Origin": "https://anything.com"})
    assert r.headers.get("access-control-allow-origin") == "https://anything.com"


def test_specific_origin_allowed(client: TestClient):
    _app_config.update(cors_origins=["https://allowed.com"])
    r = client.get("/health", headers={"Origin": "https://allowed.com"})
    assert r.headers.get("access-control-allow-origin") == "https://allowed.com"


def test_disallowed_origin_gets_no_cors_header(client: TestClient):
    _app_config.update(cors_origins=["https://allowed.com"])
    r = client.get("/health", headers={"Origin": "https://evil.com"})
    assert "access-control-allow-origin" not in r.headers


def test_no_origin_header_gets_no_cors_header(client: TestClient):
    r = client.get("/health")
    assert "access-control-allow-origin" not in r.headers


def test_preflight_returns_204(client: TestClient):
    _app_config.update(cors_origins=["https://allowed.com"])
    r = client.options(
        "/shims/",
        headers={
            "Origin": "https://allowed.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 204
    assert r.headers.get("access-control-allow-origin") == "https://allowed.com"
    assert "access-control-allow-methods" in r.headers


def test_preflight_disallowed_origin_not_handled(client: TestClient):
    _app_config.update(cors_origins=["https://allowed.com"])
    r = client.options(
        "/shims/",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in r.headers
