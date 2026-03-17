import json

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import cache
from app.db import get_session, Shim, ShimRule, WebhookLog
from app.forwarder import evaluate_rules, forward, parse_body
from app.logger import get_logger
from app.signing import verify_signature

router = APIRouter(prefix="/in", tags=["webhooks"])
logger = get_logger(__name__)

_ACCEPTED = {"received": True}


async def _forward_and_log(
    shim_id: int,
    slug: str,
    body: bytes,
    target_url: str,
    shim_headers: dict,
    session: AsyncSession,
) -> None:
    status_code, error = await forward(target_url, body, shim_headers)
    if error:
        logger.error("slug=%s forward error: %s", slug, error)
    else:
        logger.info("slug=%s forward status=%s", slug, status_code)
    log = WebhookLog(
        shim_id=shim_id,
        payload=body.decode(),
        target_url=target_url,
        status=status_code,
        error=error,
    )
    session.add(log)
    await session.commit()


@router.post("/{slug}")
async def receive_webhook(
    slug: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    body = await request.body()

    cached = cache.get(slug)
    if cached:
        shim, rules = cached
    else:
        shim = (await session.exec(select(Shim).where(Shim.slug == slug))).first()

        # Always return 200 — never reveal whether a slug exists or a signature failed
        if not shim:
            logger.warning("inbound request for unknown slug=%s", slug)
            return _ACCEPTED

        rules = list(
            (
                await session.exec(
                    select(ShimRule)
                    .where(ShimRule.shim_id == shim.id)
                    .order_by(ShimRule.order)
                )
            ).all()
        )
        cache.set(slug, shim, rules)

    # Always return 200 — never reveal whether a slug exists or a signature failed
    if not verify_signature(shim, dict(request.headers), body):
        logger.warning("signature verification failed for slug=%s", slug)
        return _ACCEPTED
    parsed = parse_body(body)
    target_url = (evaluate_rules(rules, parsed) if parsed else None) or shim.target_url

    logger.info("slug=%s forwarding to %s", slug, target_url)

    try:
        shim_headers = json.loads(shim.headers)
    except json.JSONDecodeError, ValueError:
        shim_headers = {}

    background_tasks.add_task(
        _forward_and_log, shim.id, slug, body, target_url, shim_headers, session
    )
    return _ACCEPTED
