from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session, Shim, WebhookLog

router = APIRouter(prefix="/in", tags=["webhooks"])


@router.post("/{slug}")
async def receive_webhook(
    slug: str, request: Request, session: Session = Depends(get_session)
):
    shim = session.exec(select(Shim).where(Shim.slug == slug)).first()
    if not shim:
        raise HTTPException(status_code=404, detail="Shim not found")

    body = await request.body()
    log = WebhookLog(shim_id=shim.id, payload=body.decode())
    session.add(log)
    session.commit()

    return {"slug": slug, "received": True}
