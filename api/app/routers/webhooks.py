import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import app_config as _app_config
from app import cache
from app import rate_limit
from app.db import get_session, Shim, ShimRule, ShimVariable, WebhookLog
from app.forwarder import (
    find_matching_rule,
    forward,
    parse_body,
    render_headers,
    render_template,
)
from app.logger import get_logger
from app.signing import verify_signature

router = APIRouter(prefix="/in", tags=["webhooks"])
logger = get_logger(__name__)

_ACCEPTED = {"received": True}


async def _forward_and_log(
    shim_id: int,
    slug: str,
    raw_body: bytes,
    forward_body: bytes | None,
    target_url: str,
    shim_headers: dict,
    session: AsyncSession,
    pre_error: str | None = None,
) -> None:
    """Forward the payload and write a WebhookLog entry.

    If pre_error is set (e.g. template render failure), skip forwarding and log
    the error directly without making an outbound HTTP request.
    """
    if pre_error is not None:
        logger.error("slug=%s skipping forward: %s", slug, pre_error)
        log = WebhookLog(
            shim_id=shim_id,
            payload=raw_body.decode(),
            target_url=target_url,
            status=None,
            error=pre_error,
        )
        session.add(log)
        await session.commit()
        return

    t0 = time.monotonic()
    status_code, error = await forward(target_url, forward_body, shim_headers)
    duration_ms = int((time.monotonic() - t0) * 1000)
    if error:
        logger.error("slug=%s forward error: %s", slug, error)
    else:
        logger.info("slug=%s forward status=%s", slug, status_code)
    log = WebhookLog(
        shim_id=shim_id,
        payload=raw_body.decode(),
        target_url=target_url,
        status=status_code,
        duration_ms=duration_ms,
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

    # Global hard cap — checked before any DB/cache work
    cfg = _app_config.get()
    if len(body) > cfg.max_body_size_kb * 1024:
        logger.warning(
            "slug=%s body size %d bytes exceeds global limit %d KB — dropping",
            slug,
            len(body),
            cfg.max_body_size_kb,
        )
        return _ACCEPTED

    # Lookup shim, rules, and variables — cache or DB
    cached = cache.get(slug)
    if cached:
        shim, rules, variables = cached
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
        variables = list(
            (
                await session.exec(
                    select(ShimVariable).where(ShimVariable.shim_id == shim.id)
                )
            ).all()
        )
        cache.set(slug, shim, rules, variables)

    # Rate limiting — checked before signature verification
    if shim.rate_limit_requests and shim.rate_limit_window_seconds:
        if not rate_limit.is_allowed(
            slug, shim.rate_limit_requests, shim.rate_limit_window_seconds
        ):
            logger.warning("slug=%s rate limit exceeded", slug)
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Per-shim body size override (must be ≤ global limit to have any effect)
    if shim.max_body_size_kb is not None and len(body) > shim.max_body_size_kb * 1024:
        logger.warning(
            "slug=%s body size %d bytes exceeds shim limit %d KB — dropping",
            slug,
            len(body),
            shim.max_body_size_kb,
        )
        return _ACCEPTED

    # Always return 200 — never reveal whether a slug exists or a signature failed
    if not verify_signature(shim, dict(request.headers), body):
        logger.warning("signature verification failed for slug=%s", slug)
        return _ACCEPTED

    # Resolve target URL and active body template
    parsed = parse_body(body)
    matched_rule = find_matching_rule(rules, parsed) if parsed else None
    target_url = (matched_rule.target_url if matched_rule else None) or shim.target_url
    active_template = (
        matched_rule.body_template if matched_rule else None
    ) or shim.body_template

    logger.info("slug=%s forwarding to %s", slug, target_url)

    # Build template context
    vars_dict = {v.key: v.value for v in variables}

    # Render body (falls back to raw body if no template configured)
    forward_body: bytes | None = body
    pre_error: str | None = None
    if active_template:
        try:
            forward_body = render_template(active_template, parsed or {}, vars_dict)
        except ValueError as e:
            logger.error("slug=%s template error: %s", slug, e)
            pre_error = str(e)
            forward_body = None

    # Render headers (errors fall back to {})
    shim_headers = render_headers(shim.headers, parsed or {}, vars_dict)

    background_tasks.add_task(
        _forward_and_log,
        shim.id,
        slug,
        body,
        forward_body,
        target_url,
        shim_headers,
        session,
        pre_error,
    )
    return _ACCEPTED
