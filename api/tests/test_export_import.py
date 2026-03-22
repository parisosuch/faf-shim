from fastapi.testclient import TestClient


def _create_shim(client, auth_headers, slug="my-shim"):
    r = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "My Shim", "slug": slug, "target_url": "https://example.com"},
    )
    assert r.status_code == 201
    return r.json()


def _add_rule(client, auth_headers, shim_id):
    r = client.post(
        f"/shims/{shim_id}/rules",
        headers=auth_headers,
        json={
            "order": 0,
            "field": "event",
            "operator": "==",
            "value": "push",
            "target_url": "https://example.com/push",
        },
    )
    assert r.status_code == 201
    return r.json()


def _add_variable(client, auth_headers, shim_id):
    r = client.post(
        f"/shims/{shim_id}/variables",
        headers=auth_headers,
        json={"key": "token", "value": "secret"},
    )
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_requires_auth(client: TestClient):
    r = client.get("/shims/1/export")
    assert r.status_code == 401


def test_export_not_found(client: TestClient, auth_headers):
    r = client.get("/shims/999/export", headers=auth_headers)
    assert r.status_code == 404


def test_export_basic(client: TestClient, auth_headers):
    shim = _create_shim(client, auth_headers)
    r = client.get(f"/shims/{shim['id']}/export", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "my-shim"
    assert data["target_url"] == "https://example.com"
    assert "id" not in data
    assert "created_at" not in data
    assert data["rules"] == []
    assert data["variables"] == []


def test_export_includes_rules_and_variables(client: TestClient, auth_headers):
    shim = _create_shim(client, auth_headers)
    _add_rule(client, auth_headers, shim["id"])
    _add_variable(client, auth_headers, shim["id"])

    r = client.get(f"/shims/{shim['id']}/export", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()

    assert len(data["rules"]) == 1
    rule = data["rules"][0]
    assert rule["field"] == "event"
    assert rule["operator"] == "=="
    assert rule["target_url"] == "https://example.com/push"
    assert "id" not in rule
    assert "shim_id" not in rule

    assert len(data["variables"]) == 1
    var = data["variables"][0]
    assert var["key"] == "token"
    assert var["value"] == "secret"


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def test_import_requires_auth(client: TestClient):
    r = client.post(
        "/shims/import",
        json={"name": "x", "slug": "x", "target_url": "https://x.com"},
    )
    assert r.status_code == 401


def test_import_basic(client: TestClient, auth_headers):
    payload = {
        "name": "Imported Shim",
        "slug": "imported",
        "target_url": "https://imported.example.com",
        "rules": [],
        "variables": [],
    }
    r = client.post("/shims/import", headers=auth_headers, json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "imported"
    assert data["id"] is not None


def test_import_with_rules_and_variables(client: TestClient, auth_headers):
    payload = {
        "name": "Full Shim",
        "slug": "full-shim",
        "target_url": "https://example.com",
        "rules": [
            {
                "order": 0,
                "field": "event",
                "operator": "==",
                "value": "push",
                "target_url": "https://example.com/push",
            }
        ],
        "variables": [{"key": "token", "value": "abc123"}],
    }
    r = client.post("/shims/import", headers=auth_headers, json=payload)
    assert r.status_code == 201
    data = r.json()
    assert len(data["rules"]) == 1
    assert data["rules"][0]["field"] == "event"
    assert len(data["variables"]) == 1
    assert data["variables"][0]["key"] == "token"


def test_import_duplicate_slug(client: TestClient, auth_headers):
    _create_shim(client, auth_headers, slug="taken")
    r = client.post(
        "/shims/import",
        headers=auth_headers,
        json={"name": "x", "slug": "taken", "target_url": "https://x.com"},
    )
    assert r.status_code == 409


def test_export_then_import_roundtrip(client: TestClient, auth_headers):
    shim = _create_shim(client, auth_headers, slug="original")
    _add_rule(client, auth_headers, shim["id"])
    _add_variable(client, auth_headers, shim["id"])

    export_r = client.get(f"/shims/{shim['id']}/export", headers=auth_headers)
    assert export_r.status_code == 200
    export_data = export_r.json()

    # Import under a different slug
    export_data["slug"] = "clone"
    export_data["name"] = "Clone"
    import_r = client.post("/shims/import", headers=auth_headers, json=export_data)
    assert import_r.status_code == 201
    imported = import_r.json()

    assert imported["slug"] == "clone"
    assert imported["id"] != shim["id"]
    assert len(imported["rules"]) == 1
    assert imported["rules"][0]["field"] == "event"
    assert len(imported["variables"]) == 1
    assert imported["variables"][0]["key"] == "token"
