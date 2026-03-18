from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import rate_limit


@pytest.fixture
def shim(client: TestClient, auth_headers):
    return client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "RL Shim",
            "slug": "rl-shim",
            "target_url": "https://t.com",
            "rate_limit_requests": 3,
            "rate_limit_window_seconds": 60,
        },
    ).json()


def test_requests_within_limit_return_200(client: TestClient, shim):
    for _ in range(3):
        r = client.post("/in/rl-shim", json={})
        assert r.status_code == 200


def test_request_exceeding_limit_returns_429(client: TestClient, shim):
    for _ in range(3):
        client.post("/in/rl-shim", json={})
    r = client.post("/in/rl-shim", json={})
    assert r.status_code == 429


def test_window_reset_allows_requests_again(client: TestClient, shim):
    for _ in range(3):
        client.post("/in/rl-shim", json={})
    assert client.post("/in/rl-shim", json={}).status_code == 429

    # Simulate window expiry by clearing state
    rate_limit.clear()
    assert client.post("/in/rl-shim", json={}).status_code == 200


def test_no_rate_limit_allows_unlimited(client: TestClient, auth_headers):
    client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Unlimited", "slug": "unlimited", "target_url": "https://t.com"},
    )
    for _ in range(20):
        r = client.post("/in/unlimited", json={})
        assert r.status_code == 200


def test_rate_limit_is_per_shim(client: TestClient, auth_headers):
    """Exhausting one shim's limit must not affect another shim."""
    client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Shim A",
            "slug": "rl-shim-a",
            "target_url": "https://t.com",
            "rate_limit_requests": 1,
            "rate_limit_window_seconds": 60,
        },
    )
    client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Shim B",
            "slug": "rl-shim-b",
            "target_url": "https://t.com",
            "rate_limit_requests": 1,
            "rate_limit_window_seconds": 60,
        },
    )

    client.post("/in/rl-shim-a", json={})  # exhaust shim-a
    assert client.post("/in/rl-shim-a", json={}).status_code == 429
    assert client.post("/in/rl-shim-b", json={}).status_code == 200  # shim-b unaffected


def test_window_resets_after_elapsed_time(client: TestClient, shim):
    """Verify the fixed window resets when window_seconds have passed."""
    t = 1000.0

    with patch("app.rate_limit.time") as mock_time:
        mock_time.monotonic.return_value = t
        for _ in range(3):
            client.post("/in/rl-shim", json={})
        assert client.post("/in/rl-shim", json={}).status_code == 429

        # Advance time past the window
        mock_time.monotonic.return_value = t + 61
        assert client.post("/in/rl-shim", json={}).status_code == 200
