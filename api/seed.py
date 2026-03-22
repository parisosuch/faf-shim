"""Seed the database with fake data for local development."""

import asyncio

from app.db.engine import AsyncSessionLocal, init_db
from app.db.models import Shim, ShimRule, ShimVariable, WebhookLog, RuleOperator

SHIMS = [
    {
        "shim": Shim(
            name="Coolify Deploy",
            slug="coolify-deploy",
            target_url="https://logs.example.com/generic",
            body_template='{"title": "{{ payload.resource.name }} deployment {{ payload.status }}", "description": "{{ payload.message }}"}',
            sample_payload='{"status": "success", "message": "Deployed OK", "resource": {"name": "api"}}',
        ),
        "rules": [
            ShimRule(
                order=1,
                field="status",
                operator=RuleOperator.eq,
                value="failed",
                target_url="https://pagerduty.example.com/trigger",
            ),
            ShimRule(
                order=2,
                field="status",
                operator=RuleOperator.eq,
                value="success",
                target_url="https://hooks.slack.com/services/example",
            ),
        ],
        "variables": [
            ShimVariable(key="SLACK_CHANNEL", value="deployments"),
            ShimVariable(key="BEAVER_API_KEY", value="bvr_fake_key_1234"),
        ],
    },
    {
        "shim": Shim(
            name="GitHub Webhook",
            slug="github",
            target_url="https://ci.example.com/hook",
            headers='{"X-Custom-Header": "faf-shim"}',
            secret="fake-github-secret",
            signature_header="X-Hub-Signature-256",
            signature_algorithm="sha256",
            sample_payload='{"action": "opened", "pull_request": {"title": "Fix bug", "number": 42}}',
        ),
        "rules": [
            ShimRule(
                order=1,
                field="action",
                operator=RuleOperator.eq,
                value="opened",
                target_url="https://notify.example.com/pr-opened",
            ),
            ShimRule(
                order=2,
                field="action",
                operator=RuleOperator.eq,
                value="closed",
                target_url="https://notify.example.com/pr-closed",
            ),
        ],
        "variables": [],
    },
    {
        "shim": Shim(
            name="Stripe Events",
            slug="stripe",
            target_url="https://billing.example.com/fallback",
            sample_payload='{"type": "payment_intent.succeeded", "data": {"object": {"amount": 2000}}}',
        ),
        "rules": [
            ShimRule(
                order=1,
                field="type",
                operator=RuleOperator.contains,
                value="payment_intent",
                target_url="https://billing.example.com/payment",
            ),
            ShimRule(
                order=2,
                field="type",
                operator=RuleOperator.contains,
                value="customer",
                target_url="https://crm.example.com/stripe",
            ),
        ],
        "variables": [
            ShimVariable(key="STRIPE_WEBHOOK_SECRET", value="whsec_fake1234"),
        ],
    },
]

LOGS_PER_SHIM = 5


async def seed() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        for entry in SHIMS:
            shim = entry["shim"]
            session.add(shim)
            await session.flush()

            for rule in entry["rules"]:
                rule.shim_id = shim.id
                session.add(rule)

            for var in entry["variables"]:
                var.shim_id = shim.id
                session.add(var)

            for i in range(LOGS_PER_SHIM):
                session.add(
                    WebhookLog(
                        shim_id=shim.id,
                        payload='{"status": "success"}',
                        target_url=shim.target_url,
                        status=200 if i % 4 != 0 else 500,
                        duration_ms=100 + i * 20,
                    )
                )

        await session.commit()

    print(f"Seeded {len(SHIMS)} shims with rules, variables, and logs.")


if __name__ == "__main__":
    asyncio.run(seed())
