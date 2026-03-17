import json

import httpx

from app.db.models import RuleOperator, ShimRule


def _resolve_field(body: dict, path: str):
    """Walk a dot-separated path into a dict, returning None if any step is missing."""
    current = body
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def evaluate_rules(rules: list[ShimRule], body: dict) -> str | None:
    """Return the target_url of the first matching rule, or None if none match."""
    for rule in rules:
        value = _resolve_field(body, rule.field)
        if value is None:
            continue
        str_value = str(value)
        if rule.operator == RuleOperator.eq and str_value == rule.value:
            return rule.target_url
        if rule.operator == RuleOperator.neq and str_value != rule.value:
            return rule.target_url
        if rule.operator == RuleOperator.contains and rule.value in str_value:
            return rule.target_url
    return None


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
