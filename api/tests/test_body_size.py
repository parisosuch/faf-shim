from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app_config as _app_config


@pytest.fixture(autouse=True)
def reset_app_config():
    yield
    _app_config.update(max_body_size_kb=1024)


@pytest.fixture
def shim(client: TestClient, auth_headers):
    return client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Size Shim", "slug": "size-shim", "target_url": "https://t.com"},
    ).json()


def test_body_within_global_limit_is_forwarded(client: TestClient, auth_headers, shim):
    _app_config.update(max_body_size_kb=1)
    body = b"x" * 512  # 512 bytes — under 1 KB
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post("/in/size-shim", content=body)
    assert r.status_code == 200
    assert r.json()["received"] is True
    assert mock_fwd.call_count == 1


def test_body_exceeds_global_limit_is_dropped(client: TestClient, auth_headers, shim):
    _app_config.update(max_body_size_kb=1)
    body = b"x" * 1025  # 1025 bytes — over 1 KB
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post("/in/size-shim", content=body)
    assert r.status_code == 200
    assert r.json()["received"] is True
    # Silently dropped — forward never called
    assert mock_fwd.call_count == 0


def test_per_shim_body_size_stricter_than_global(client: TestClient, auth_headers):
    """Per-shim limit tighter than global drops oversized requests."""
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Strict Shim",
            "slug": "strict-shim",
            "target_url": "https://t.com",
            "max_body_size_kb": 1,
        },
    ).json()
    assert shim["max_body_size_kb"] == 1

    body = b"x" * 1025  # over 1 KB, under global 1024 KB
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post("/in/strict-shim", content=body)
    assert r.status_code == 200
    assert mock_fwd.call_count == 0


def test_per_shim_body_size_within_shim_limit_is_forwarded(
    client: TestClient, auth_headers
):
    """Body within the per-shim limit is forwarded normally."""
    client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Strict Shim 2",
            "slug": "strict-shim-2",
            "target_url": "https://t.com",
            "max_body_size_kb": 1,
        },
    )
    body = b"x" * 512  # under 1 KB shim limit
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post("/in/strict-shim-2", content=body)
    assert r.status_code == 200
    assert mock_fwd.call_count == 1


def test_unknown_slug_body_still_size_checked(client: TestClient):
    """Unknown slugs still get the global body size check."""
    _app_config.update(max_body_size_kb=1)
    body = b"x" * 1025
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post("/in/unknown-slug", content=body)
    assert r.status_code == 200
    assert mock_fwd.call_count == 0
