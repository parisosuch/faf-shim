from fastapi import APIRouter, Request

router = APIRouter(prefix="/webhook", tags=["webhooks"])


@router.post("/{shim_id}")
async def receive_webhook(shim_id: str, request: Request):
    body = await request.json()
    return {"shim_id": shim_id, "received": body}
