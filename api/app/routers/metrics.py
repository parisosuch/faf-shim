from datetime import timedelta
from enum import Enum

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.utils import now

from app import cache
from app.auth import require_auth
from app.db import get_session
from app.db.models import Shim, WebhookLog

router = APIRouter(
    prefix="/metrics", tags=["metrics"], dependencies=[Depends(require_auth)]
)


class BucketSize(str, Enum):
    hour = "hour"
    day = "day"
    week = "week"
    month = "month"


_STRFTIME = {
    BucketSize.hour: "%Y-%m-%d %H:00",
    BucketSize.day: "%Y-%m-%d",
    BucketSize.week: "%Y-%W",
    BucketSize.month: "%Y-%m",
}

_CUTOFF_DELTA = {
    BucketSize.hour: lambda n: timedelta(hours=n),
    BucketSize.day: lambda n: timedelta(days=n),
    BucketSize.week: lambda n: timedelta(weeks=n),
    BucketSize.month: lambda n: timedelta(days=n * 30),
}


@router.get("/")
async def get_metrics(
    bucket: BucketSize = BucketSize.day,
    range_: int = Query(default=30, alias="range", ge=1),
    session: AsyncSession = Depends(get_session),
):
    cutoff = now() - _CUTOFF_DELTA[bucket](range_)
    strftime_fmt = _STRFTIME[bucket]

    # --- Aggregate totals per shim (all-time) ---
    totals_stmt = (
        select(
            Shim.id,
            Shim.slug,
            Shim.name,
            func.count(WebhookLog.id).label("total_requests"),
            func.count(case((WebhookLog.status.between(200, 299), 1))).label(
                "successful_forwards"
            ),
            func.count(case((WebhookLog.error.isnot(None), 1))).label(
                "failed_forwards"
            ),
            func.avg(WebhookLog.duration_ms).label("avg_duration_ms"),
            func.max(WebhookLog.received_at).label("last_triggered_at"),
        )
        .outerjoin(WebhookLog, Shim.id == WebhookLog.shim_id)
        .group_by(Shim.id)
    )
    totals = (await session.exec(totals_stmt)).all()

    # --- Time-bucketed counts within the requested range ---
    bucket_expr = func.strftime(strftime_fmt, WebhookLog.received_at)
    buckets_stmt = (
        select(
            WebhookLog.shim_id,
            bucket_expr.label("bucket"),
            func.count(WebhookLog.id).label("requests"),
            func.count(case((WebhookLog.status.between(200, 299), 1))).label(
                "successful_forwards"
            ),
            func.count(case((WebhookLog.error.isnot(None), 1))).label(
                "failed_forwards"
            ),
            func.avg(WebhookLog.duration_ms).label("avg_duration_ms"),
        )
        .where(WebhookLog.received_at >= cutoff)
        .group_by(WebhookLog.shim_id, bucket_expr)
        .order_by(bucket_expr)
    )
    bucket_rows = (await session.exec(buckets_stmt)).all()

    # Group bucket rows by shim_id and accumulate global buckets
    shim_buckets: dict[int, list[dict]] = {}
    global_buckets: dict[str, dict] = {}

    for row in bucket_rows:
        entry = {
            "bucket": row.bucket,
            "requests": row.requests,
            "successful_forwards": row.successful_forwards,
            "failed_forwards": row.failed_forwards,
            "avg_duration_ms": (
                round(row.avg_duration_ms, 2) if row.avg_duration_ms else None
            ),
        }
        shim_buckets.setdefault(row.shim_id, []).append(entry)

        g = global_buckets.setdefault(
            row.bucket,
            {
                "bucket": row.bucket,
                "requests": 0,
                "successful_forwards": 0,
                "failed_forwards": 0,
                "_duration_sum": 0.0,
                "_duration_count": 0,
            },
        )
        g["requests"] += row.requests
        g["successful_forwards"] += row.successful_forwards
        g["failed_forwards"] += row.failed_forwards
        if row.avg_duration_ms:
            g["_duration_sum"] += row.avg_duration_ms * row.requests
            g["_duration_count"] += row.requests

    global_bucket_list = []
    for b in sorted(global_buckets.values(), key=lambda x: x["bucket"]):
        global_bucket_list.append(
            {
                "bucket": b["bucket"],
                "requests": b["requests"],
                "successful_forwards": b["successful_forwards"],
                "failed_forwards": b["failed_forwards"],
                "avg_duration_ms": (
                    round(b["_duration_sum"] / b["_duration_count"], 2)
                    if b["_duration_count"]
                    else None
                ),
            }
        )

    # Build per-shim metrics and accumulate global totals
    shim_metrics = []
    g_requests = g_successful = g_failed = g_dur_count = 0
    g_dur_sum = 0.0

    for row in totals:
        shim_metrics.append(
            {
                "shim_id": row.id,
                "slug": row.slug,
                "name": row.name,
                "total_requests": row.total_requests,
                "successful_forwards": row.successful_forwards,
                "failed_forwards": row.failed_forwards,
                "avg_duration_ms": (
                    round(row.avg_duration_ms, 2) if row.avg_duration_ms else None
                ),
                "last_triggered_at": row.last_triggered_at,
                "buckets": shim_buckets.get(row.id, []),
            }
        )
        g_requests += row.total_requests
        g_successful += row.successful_forwards
        g_failed += row.failed_forwards
        if row.avg_duration_ms and row.total_requests:
            g_dur_sum += row.avg_duration_ms * row.total_requests
            g_dur_count += row.total_requests

    cache_hits, cache_misses = cache.get_stats()

    return {
        "global": {
            "total_requests": g_requests,
            "successful_forwards": g_successful,
            "failed_forwards": g_failed,
            "avg_duration_ms": (
                round(g_dur_sum / g_dur_count, 2) if g_dur_count else None
            ),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "buckets": global_bucket_list,
        },
        "shims": shim_metrics,
    }
