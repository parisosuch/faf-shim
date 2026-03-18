import json

import httpx
from jinja2 import Environment, StrictUndefined

from app.db.models import RuleOperator, ShimRule

_env = Environment(undefined=StrictUndefined)


def _resolve_field(body: dict, path: str):
    """Walk a dot-separated path into a dict, returning None if any step is missing."""
    current = body
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def find_matching_rule(rules: list[ShimRule], body: dict) -> ShimRule | None:
    """Return the first rule that matches the body, or None."""
    for rule in rules:
        value = _resolve_field(body, rule.field)
        if value is None:
            continue
        str_value = str(value)
        if rule.operator == RuleOperator.eq and str_value == rule.value:
            return rule
        if rule.operator == RuleOperator.neq and str_value != rule.value:
            return rule
        if rule.operator == RuleOperator.contains and rule.value in str_value:
            return rule
    return None


def evaluate_rules(rules: list[ShimRule], body: dict) -> str | None:
    """Return the target_url of the first matching rule, or None if none match."""
    rule = find_matching_rule(rules, body)
    return rule.target_url if rule else None


def render_template(template: str, payload: dict, variables: dict) -> bytes:
    """Render a Jinja2 template against payload and vars context.

    Context keys:
      payload  — the parsed incoming JSON body
      vars     — the shim's stored variables (key/value pairs)

    Raises ValueError on render errors (undefined variable, syntax error, etc.).
    """
    try:
        return (
            _env.from_string(template).render(payload=payload, vars=variables).encode()
        )
    except Exception as e:
        raise ValueError(f"Template render error: {e}") from e


def render_headers(headers_json: str, payload: dict, variables: dict) -> dict:
    """Render the headers JSON string as a Jinja2 template, then parse as JSON.

    This allows header values to reference payload fields or stored variables,
    e.g. {"Authorization": "Bearer {{ vars.API_KEY }}"}.

    Returns {} on any render or parse error so forwarding is never blocked by a
    misconfigured headers template.
    """
    try:
        rendered = _env.from_string(headers_json).render(
            payload=payload, vars=variables
        )
        return json.loads(rendered)
    except Exception:
        return {}


async def forward(
    target_url: str, body: bytes, headers: dict
) -> tuple[int | None, str | None]:
    """POST the payload to target_url. Returns (status_code, error_message)."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(target_url, content=body, headers=headers, timeout=10)
            return r.status_code, None
    except Exception as e:
        return None, str(e)


def parse_body(raw: bytes) -> dict | None:
    """Try to parse raw bytes as JSON. Returns None if not valid JSON."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError, ValueError:
        return None
