from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.db import get_session, Shim, WebhookLog
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

    log = WebhookLog(shim_id=shim.id, payload=body.decode())
    session.add(log)
    session.commit()

    return _ACCEPTED
