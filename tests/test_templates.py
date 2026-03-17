"""Tests for body template rendering and header template rendering."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def shim_with_template(client: TestClient, auth_headers):
    return client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Tmpl",
            "slug": "tmpl",
            "target_url": "https://target.com",
            "body_template": '{"title": "{{ payload.event }}", "static": "hello"}',
        },
    ).json()


# ---------------------------------------------------------------------------
# Body template rendering
# ---------------------------------------------------------------------------


def test_shim_body_template_transforms_forwarded_body(
    client: TestClient, auth_headers, shim_with_template
):
    """Shim-level template reshapes the outgoing body."""
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post("/in/tmpl", json={"event": "push"})
        assert r.status_code == 200
        forwarded = json.loads(mock_fwd.call_args[0][1])
        assert forwarded == {"title": "push", "static": "hello"}


def test_no_template_forwards_raw_body(client: TestClient, auth_headers):
    """Without a template the raw request body is forwarded unchanged."""
    client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "Raw", "slug": "raw", "target_url": "https://target.com"},
    )
    raw = b'{"event": "push"}'
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post(
            "/in/raw", content=raw, headers={"Content-Type": "application/json"}
        )
        assert mock_fwd.call_args[0][1] == raw


def test_template_uses_variables(client: TestClient, auth_headers):
    """Variables stored on the shim are available in the template context."""
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Vars",
            "slug": "vars-tmpl",
            "target_url": "https://target.com",
            "body_template": '{"api_key": "{{ vars.MY_KEY }}", "event": "{{ payload.event }}"}',
        },
    ).json()
    client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "MY_KEY", "value": "secret123"},
    )

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/vars-tmpl", json={"event": "deploy"})
        forwarded = json.loads(mock_fwd.call_args[0][1])
        assert forwarded["api_key"] == "secret123"
        assert forwarded["event"] == "deploy"


def test_rule_body_template_overrides_shim_template(client: TestClient, auth_headers):
    """A rule-level body_template takes precedence over the shim-level one."""
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Override",
            "slug": "override",
            "target_url": "https://target.com",
            "body_template": '{"from": "shim"}',
        },
    ).json()
    client.post(
        f"/shims/{shim['id']}/rules",
        headers=auth_headers,
        json={
            "field": "status",
            "operator": "==",
            "value": "failed",
            "target_url": "https://alerts.com",
            "body_template": '{"from": "rule", "status": "{{ payload.status }}"}',
        },
    )

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/override", json={"status": "failed"})
        forwarded = json.loads(mock_fwd.call_args[0][1])
        assert forwarded["from"] == "rule"
        assert forwarded["status"] == "failed"


def test_shim_template_used_when_rule_has_no_template(client: TestClient, auth_headers):
    """When the matched rule has no body_template, fall back to the shim template."""
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Fallback",
            "slug": "fallback-tmpl",
            "target_url": "https://target.com",
            "body_template": '{"from": "shim", "event": "{{ payload.event }}"}',
        },
    ).json()
    client.post(
        f"/shims/{shim['id']}/rules",
        headers=auth_headers,
        json={
            "field": "event",
            "operator": "==",
            "value": "push",
            "target_url": "https://push-target.com",
            # no body_template on the rule
        },
    )

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/fallback-tmpl", json={"event": "push"})
        forwarded = json.loads(mock_fwd.call_args[0][1])
        assert forwarded["from"] == "shim"
        assert forwarded["event"] == "push"


def test_template_error_skips_forward_and_logs_error(client: TestClient, auth_headers):
    """A template referencing an undefined variable skips forwarding and writes an error log."""
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Bad Tmpl",
            "slug": "bad-tmpl",
            "target_url": "https://target.com",
            "body_template": "{{ vars.UNDEFINED_VAR }}",
        },
    ).json()

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post("/in/bad-tmpl", json={"event": "push"})
        assert r.status_code == 200
        mock_fwd.assert_not_awaited()

    logs = client.get(f"/shims/{shim['id']}/logs", headers=auth_headers).json()
    assert len(logs) == 1
    assert logs[0]["error"] is not None
    assert logs[0]["status"] is None


def test_template_nested_payload_field(client: TestClient, auth_headers):
    """Dot-path fields in the incoming payload are accessible via payload.field notation."""
    client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Nested",
            "slug": "nested-tmpl",
            "target_url": "https://target.com",
            "body_template": '{"state": "{{ payload.deployment.state }}"}',
        },
    )

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/nested-tmpl", json={"deployment": {"state": "failed"}})
        forwarded = json.loads(mock_fwd.call_args[0][1])
        assert forwarded["state"] == "failed"


# ---------------------------------------------------------------------------
# Header template rendering
# ---------------------------------------------------------------------------


def test_headers_template_injects_variable(client: TestClient, auth_headers):
    """Header values are rendered as Jinja2 templates — useful for injecting API keys."""
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Hdr",
            "slug": "hdr-tmpl",
            "target_url": "https://target.com",
            "headers": '{"Authorization": "Bearer {{ vars.TOKEN }}"}',
        },
    ).json()
    client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "TOKEN", "value": "mytoken"},
    )

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/hdr-tmpl", json={"event": "push"})
        forwarded_headers = mock_fwd.call_args[0][2]
        assert forwarded_headers["Authorization"] == "Bearer mytoken"


def test_static_headers_still_work(client: TestClient, auth_headers):
    """Plain (non-template) header JSON continues to work after the template change."""
    client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Static Hdr",
            "slug": "static-hdr",
            "target_url": "https://target.com",
            "headers": '{"X-Custom": "value123"}',
        },
    )

    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/static-hdr", json={"event": "push"})
        forwarded_headers = mock_fwd.call_args[0][2]
        assert forwarded_headers["X-Custom"] == "value123"


# ---------------------------------------------------------------------------
# Test dry-run endpoint
# ---------------------------------------------------------------------------


def test_test_endpoint_returns_rendered_body(client: TestClient, auth_headers):
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Dry Run",
            "slug": "dry-run",
            "target_url": "https://target.com",
            "body_template": '{"event": "{{ payload.type }}", "repo": "{{ payload.repo }}"}',
        },
    ).json()

    r = client.post(
        f"/shims/{shim['id']}/test",
        headers=auth_headers,
        json={"payload": {"type": "push", "repo": "my-repo"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert json.loads(data["rendered_body"]) == {"event": "push", "repo": "my-repo"}


def test_test_endpoint_no_template_returns_null_rendered_body(
    client: TestClient, auth_headers
):
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={"name": "NoT", "slug": "no-tmpl", "target_url": "https://target.com"},
    ).json()

    r = client.post(
        f"/shims/{shim['id']}/test",
        headers=auth_headers,
        json={"payload": {"event": "push"}},
    )
    assert r.status_code == 200
    assert r.json()["rendered_body"] is None


def test_test_endpoint_template_error_returns_error_string(
    client: TestClient, auth_headers
):
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Err",
            "slug": "err-tmpl",
            "target_url": "https://target.com",
            "body_template": "{{ vars.MISSING }}",
        },
    ).json()

    r = client.post(
        f"/shims/{shim['id']}/test",
        headers=auth_headers,
        json={"payload": {}},
    )
    assert r.status_code == 200
    assert "Template error" in r.json()["rendered_body"]


def test_test_endpoint_uses_variables(client: TestClient, auth_headers):
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "VarTest",
            "slug": "var-test-tmpl",
            "target_url": "https://target.com",
            "body_template": '{"key": "{{ vars.MY_KEY }}"}',
        },
    ).json()
    client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "MY_KEY", "value": "abc"},
    )

    r = client.post(
        f"/shims/{shim['id']}/test",
        headers=auth_headers,
        json={"payload": {}},
    )
    assert r.status_code == 200
    assert json.loads(r.json()["rendered_body"])["key"] == "abc"


def test_test_endpoint_returns_rendered_headers(client: TestClient, auth_headers):
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "HdrTest",
            "slug": "hdr-test",
            "target_url": "https://target.com",
            "headers": '{"Authorization": "Bearer {{ vars.TOKEN }}"}',
        },
    ).json()
    client.post(
        f"/shims/{shim['id']}/variables",
        headers=auth_headers,
        json={"key": "TOKEN", "value": "tok123"},
    )

    r = client.post(
        f"/shims/{shim['id']}/test",
        headers=auth_headers,
        json={"payload": {}},
    )
    assert r.status_code == 200
    assert r.json()["rendered_headers"]["Authorization"] == "Bearer tok123"
