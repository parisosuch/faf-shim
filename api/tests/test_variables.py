import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def shim(client: TestClient, auth_headers):
    return client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Var Shim",
            "slug": "var-shim",
            "target_url": "https://target.com",
        },
    ).json()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_create_variable(client: TestClient, auth_headers, shim):
    r = client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "API_KEY", "value": "secret123"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["key"] == "API_KEY"
    assert data["value"] == "secret123"
    assert data["shim_id"] == shim["id"]


def test_create_variable_shim_not_found(client: TestClient, auth_headers):
    r = client.post(
        "/shims/999/variables",
        headers=auth_headers,
        json={"key": "K", "value": "V"},
    )
    assert r.status_code == 404


def test_list_variables(client: TestClient, auth_headers, shim):
    client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "K1", "value": "V1"},
    )
    client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "K2", "value": "V2"},
    )
    r = client.get(f"/shims/{shim['id']}/variables", headers=auth_headers)
    assert r.status_code == 200
    keys = [v["key"] for v in r.json()]
    assert "K1" in keys
    assert "K2" in keys


def test_list_variables_shim_not_found(client: TestClient, auth_headers):
    r = client.get("/shims/999/variables", headers=auth_headers)
    assert r.status_code == 404


def test_update_variable(client: TestClient, auth_headers, shim):
    var = client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "TOKEN", "value": "old"},
    ).json()
    r = client.patch(
        f"/shims/{shim['id']}/variables/{var['id']}",
        headers=auth_headers,
        json={"value": "new"},
    )
    assert r.status_code == 200
    assert r.json()["value"] == "new"
    assert r.json()["key"] == "TOKEN"  # unchanged


def test_update_variable_not_found(client: TestClient, auth_headers, shim):
    r = client.patch(
        f"/shims/{shim['id']}/variables/999",
        headers=auth_headers,
        json={"value": "x"},
    )
    assert r.status_code == 404


def test_update_variable_wrong_shim(client: TestClient, auth_headers, shim):
    other = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Other", "slug": "other-var", "target_url": "https://other.com"},
    ).json()
    var = client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "K", "value": "V"},
    ).json()
    r = client.patch(
        f"/shims/{other['id']}/variables/{var['id']}",
        headers=auth_headers,
        json={"value": "x"},
    )
    assert r.status_code == 404


def test_delete_variable(client: TestClient, auth_headers, shim):
    var = client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "K", "value": "V"},
    ).json()
    r = client.delete(
        f"/shims/{shim['id']}/variables/{var['id']}", headers=auth_headers
    )
    assert r.status_code == 204
    remaining = client.get(
        f"/shims/{shim['id']}/variables", headers=auth_headers
    ).json()
    assert all(v["id"] != var["id"] for v in remaining)


def test_delete_variable_not_found(client: TestClient, auth_headers, shim):
    r = client.delete(f"/shims/{shim['id']}/variables/999", headers=auth_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Serialization in ShimRead
# ---------------------------------------------------------------------------


def test_get_shim_includes_variables(client: TestClient, auth_headers, shim):
    client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "MY_KEY", "value": "abc"},
    )
    r = client.get(f"/shims/{shim['id']}", headers=auth_headers)
    assert r.status_code == 200
    variables = r.json()["variables"]
    assert len(variables) == 1
    assert variables[0]["key"] == "MY_KEY"
    assert variables[0]["value"] == "abc"


def test_list_shims_includes_variables(client: TestClient, auth_headers, shim):
    client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "K", "value": "V"},
    )
    r = client.get("/shims/", headers=auth_headers)
    assert r.status_code == 200
    match = next(s for s in r.json() if s["slug"] == "var-shim")
    assert len(match["variables"]) == 1


def test_delete_shim_cascades_variables(client: TestClient, auth_headers, shim):
    client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "K", "value": "V"},
    )
    client.delete(f"/shims/{shim['id']}", headers=auth_headers)
    # Shim is gone so /variables returns 404
    r = client.get(f"/shims/{shim['id']}/variables", headers=auth_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------


def test_variable_update_invalidates_cache(client: TestClient, auth_headers):
    """Updating a variable clears the slug cache so the next request picks up the change."""
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Cache V",
            "slug": "cache-var",
            "target_url": "https://target.com",
            "body_template": '{"key": "{{ vars.MY_KEY }}"}',
        },
    ).json()
    var = client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "MY_KEY", "value": "v1"},
    ).json()

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/cache-var", json={})
        assert json.loads(mock_fwd.call_args[0][1])["key"] == "v1"

    client.patch(
        f"/shims/{shim['id']}/variables/{var['id']}",
        headers=auth_headers,
        json={"value": "v2"},
    )

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/cache-var", json={})
        assert json.loads(mock_fwd.call_args[0][1])["key"] == "v2"
