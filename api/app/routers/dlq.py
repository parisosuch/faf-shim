import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth import require_auth
from app.db import get_session, Shim, DeadLetter
from app.forwarder import forward
from app.logger import get_logger
from app.utils import now

router = APIRouter(prefix="/dlq", tags=["dlq"], dependencies=[Depends(require_auth)])
logger = get_logger(__name__)


@router.get("/", response_model=list[DeadLetter])
async def list_dlq(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    return (
        await session.exec(
            select(DeadLetter)
            .order_by(DeadLetter.failed_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()


@router.get("/{shim_id}", response_model=list[DeadLetter])
async def list_dlq_for_shim(
    shim_id: int,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    if not await session.get(Shim, shim_id):
        raise HTTPException(status_code=404, detail="Shim not found")
    return (
        await session.exec(
            select(DeadLetter)
            .where(DeadLetter.shim_id == shim_id)
            .order_by(DeadLetter.failed_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()


@router.post("/{dlq_id}/replay", response_model=DeadLetter)
async def replay(
    dlq_id: int,
    session: AsyncSession = Depends(get_session),
):
    entry = await session.get(DeadLetter, dlq_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Dead letter entry not found")

    headers = json.loads(entry.headers)
    status_code, error = await forward(
        entry.target_url, entry.payload.encode(), headers
    )

    entry.replayed_at = now()
    entry.replay_status = status_code
    entry.replay_error = error
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    if error:
        logger.warning("dlq id=%d replay error: %s", dlq_id, error)
    else:
        logger.info("dlq id=%d replayed status=%s", dlq_id, status_code)

    return entry
