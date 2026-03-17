from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.forwarder import (
    evaluate_rules,
    find_matching_rule,
    parse_body,
    render_template,
)
from app.db.models import ShimRule, RuleOperator


# --- Unit tests for rule evaluation ---


def _rule(field, operator, value, target_url, order=0):
    return ShimRule(
        id=1,
        shim_id=1,
        order=order,
        field=field,
        operator=operator,
        value=value,
        target_url=target_url,
    )


def test_evaluate_rules_eq_match():
    rules = [_rule("status", RuleOperator.eq, "failed", "https://pagerduty.com")]
    assert evaluate_rules(rules, {"status": "failed"}) == "https://pagerduty.com"


def test_evaluate_rules_eq_no_match():
    rules = [_rule("status", RuleOperator.eq, "failed", "https://pagerduty.com")]
    assert evaluate_rules(rules, {"status": "success"}) is None


def test_evaluate_rules_neq_match():
    rules = [_rule("status", RuleOperator.neq, "success", "https://logs.com")]
    assert evaluate_rules(rules, {"status": "failed"}) == "https://logs.com"


def test_evaluate_rules_contains_match():
    rules = [_rule("message", RuleOperator.contains, "error", "https://alerts.com")]
    assert (
        evaluate_rules(rules, {"message": "deployment error occurred"})
        == "https://alerts.com"
    )


def test_evaluate_rules_contains_no_match():
    rules = [_rule("message", RuleOperator.contains, "error", "https://alerts.com")]
    assert evaluate_rules(rules, {"message": "deployment succeeded"}) is None


def test_evaluate_rules_first_match_wins():
    rules = [
        _rule("status", RuleOperator.eq, "failed", "https://first.com", order=0),
        _rule("status", RuleOperator.eq, "failed", "https://second.com", order=1),
    ]
    assert evaluate_rules(rules, {"status": "failed"}) == "https://first.com"


def test_evaluate_rules_nested_field():
    rules = [_rule("deployment.state", RuleOperator.eq, "error", "https://alerts.com")]
    assert (
        evaluate_rules(rules, {"deployment": {"state": "error"}})
        == "https://alerts.com"
    )


def test_evaluate_rules_missing_field_skipped():
    rules = [_rule("missing.field", RuleOperator.eq, "x", "https://x.com")]
    assert evaluate_rules(rules, {"status": "ok"}) is None


# --- Unit tests for find_matching_rule ---


def test_find_matching_rule_returns_rule_object():
    rule = _rule("status", RuleOperator.eq, "failed", "https://alerts.com")
    result = find_matching_rule([rule], {"status": "failed"})
    assert result is rule


def test_find_matching_rule_no_match():
    rule = _rule("status", RuleOperator.eq, "failed", "https://alerts.com")
    assert find_matching_rule([rule], {"status": "ok"}) is None


def test_find_matching_rule_empty_rules():
    assert find_matching_rule([], {"status": "ok"}) is None


def test_evaluate_rules_delegates_to_find_matching_rule():
    rule = _rule("status", RuleOperator.eq, "failed", "https://alerts.com")
    assert evaluate_rules([rule], {"status": "failed"}) == "https://alerts.com"


# --- Unit tests for render_template ---


def test_render_template_basic():
    result = render_template('{"event": "{{ payload.type }}"}', {"type": "push"}, {})
    assert result == b'{"event": "push"}'


def test_render_template_with_variables():
    result = render_template('{"key": "{{ vars.API_KEY }}"}', {}, {"API_KEY": "secret"})
    assert result == b'{"key": "secret"}'


def test_render_template_static_value():
    result = render_template('{"project": "Cove"}', {}, {})
    assert result == b'{"project": "Cove"}'


def test_render_template_undefined_variable_raises():
    with pytest.raises(ValueError, match="Template render error"):
        render_template("{{ vars.MISSING }}", {}, {})


def test_render_template_returns_bytes():
    result = render_template("hello", {}, {})
    assert isinstance(result, bytes)


def test_parse_body_valid_json():
    assert parse_body(b'{"status": "ok"}') == {"status": "ok"}


def test_parse_body_invalid_json():
    assert parse_body(b"not json") is None


# --- Integration tests for the webhook handler ---


@pytest.fixture
def shim_with_rules(client: TestClient, auth_headers):
    shim = client.post(
        "/shims/",
        headers=auth_headers,
        json={
            "name": "Forwarder",
            "slug": "forwarder",
            "target_url": "https://fallback.com",
        },
    ).json()
    client.post(
        f"/shims/{shim['id']}/rules",
        headers=auth_headers,
        json={
            "field": "status",
            "operator": "==",
            "value": "failed",
            "target_url": "https://pagerduty.com",
            "order": 0,
        },
    )
    client.post(
        f"/shims/{shim['id']}/rules",
        headers=auth_headers,
        json={
            "field": "status",
            "operator": "==",
            "value": "success",
            "target_url": "https://slack.com",
            "order": 1,
        },
    )
    return shim


def test_forwards_to_matching_rule(client: TestClient, shim_with_rules):
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post("/in/forwarder", json={"status": "failed"})
        assert r.status_code == 200
        mock_fwd.assert_awaited_once()
        assert mock_fwd.call_args[0][0] == "https://pagerduty.com"


def test_forwards_to_fallback_when_no_rule_matches(client: TestClient, shim_with_rules):
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        r = client.post("/in/forwarder", json={"status": "unknown"})
        assert r.status_code == 200
        assert mock_fwd.call_args[0][0] == "https://fallback.com"


def test_forwards_to_fallback_for_non_json_body(client: TestClient, shim_with_rules):
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (200, None)
        client.post("/in/forwarder", content=b"plain text body")
        assert mock_fwd.call_args[0][0] == "https://fallback.com"


def test_logs_forward_status(client: TestClient, auth_headers, shim_with_rules):
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (201, None)
        client.post("/in/forwarder", json={"status": "success"})
        mock_fwd.assert_awaited_once()
        assert mock_fwd.call_args[0][0] == "https://slack.com"


def test_logs_forward_error(client: TestClient, shim_with_rules):
    with patch("app.routers.webhooks.forward", new_callable=AsyncMock) as mock_fwd:
        mock_fwd.return_value = (None, "connection refused")
        r = client.post("/in/forwarder", json={"status": "failed"})
        assert r.status_code == 200  # still returns 200 to caller
