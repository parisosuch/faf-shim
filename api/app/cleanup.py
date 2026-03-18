"""Periodic task that deletes webhook logs outside the retention window."""

import asyncio
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import app_config as _app_config
from app.db import AsyncSessionLocal
from app.db.models import Shim, WebhookLog, _now
from app.logger import get_logger

logger = get_logger(__name__)


async def delete_old_logs(session: AsyncSession) -> int:
    """Delete logs that fall outside each shim's retention window.

    Groups shims by their effective retention value so we issue one DELETE
    per unique retention period rather than one per shim.
    Returns the total number of rows deleted.
    """
    cfg = _app_config.get()
    global_retention = cfg.log_retention_days
    now = _now()

    shims = (await session.exec(select(Shim.id, Shim.log_retention_days))).all()

    # Map retention_days -> [shim_ids]; skip retention=0 (keep forever).
    by_retention: dict[int, list[int]] = defaultdict(list)
    for shim_id, shim_retention in shims:
        effective = shim_retention if shim_retention is not None else global_retention
        if effective > 0:
            by_retention[effective].append(shim_id)

    deleted = 0
    for retention_days, shim_ids in by_retention.items():
        cutoff = now - timedelta(days=retention_days)
        result = await session.exec(
            delete(WebhookLog)
            .where(WebhookLog.shim_id.in_(shim_ids))
            .where(WebhookLog.received_at < cutoff)
        )
        deleted += result.rowcount

    await session.commit()
    return deleted


async def start_cleanup_loop() -> None:
    """Run delete_old_logs on the interval configured in AppConfig."""
    while True:
        interval = _app_config.get().cleanup_interval_seconds
        await asyncio.sleep(interval)
        try:
            async with AsyncSessionLocal() as session:
                deleted = await delete_old_logs(session)
            logger.info("cleanup: deleted %d old log(s)", deleted)
        except Exception:
            logger.exception("cleanup: error during log cleanup")
