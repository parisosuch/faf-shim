import json

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.db import get_session, Shim, ShimRule, WebhookLog
from app.forwarder import evaluate_rules, forward, parse_body
from app.signing import verify_signature

router = APIRouter(prefix="/in", tags=["webhooks"])

_ACCEPTED = {"received": True}


@router.post("/{slug}")
async def receive_webhook(
    slug: str, request: Request, session: Session = Depends(get_session)
):
    body = await request.body()
    shim = session.exec(select(Shim).where(Shim.slug == slug)).first()

    # Always return 200 — never reveal whether a slug exists or a signature failed
    if not shim or not verify_signature(shim, dict(request.headers), body):
        return _ACCEPTED

    # Resolve target URL from rules, falling back to shim default
    rules = session.exec(
        select(ShimRule).where(ShimRule.shim_id == shim.id).order_by(ShimRule.order)
    ).all()
    parsed = parse_body(body)
    target_url = (evaluate_rules(rules, parsed) if parsed else None) or shim.target_url

    # Forward the payload
    try:
        shim_headers = json.loads(shim.headers)
    except json.JSONDecodeError, ValueError:
        shim_headers = {}

    status_code, error = await forward(target_url, body, shim_headers)

    log = WebhookLog(
        shim_id=shim.id, payload=body.decode(), status=status_code, error=error
    )
    session.add(log)
    session.commit()

    return _ACCEPTED
