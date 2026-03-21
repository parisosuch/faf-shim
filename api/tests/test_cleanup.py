from datetime import timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import app_config as _app_config
from app.cleanup import delete_old_logs
from app.db.models import Shim, WebhookLog
from app.utils import now


@pytest.fixture(autouse=True)
def reset_app_config():
    yield
    _app_config.update(log_retention_days=30)


async def _make_shim(
    session: AsyncSession, slug: str, retention: int | None = None
) -> Shim:
    shim = Shim(
        name=slug, slug=slug, target_url="https://t.com", log_retention_days=retention
    )
    session.add(shim)
    await session.commit()
    await session.refresh(shim)
    return shim


async def _make_log(session: AsyncSession, shim_id: int, days_ago: int) -> WebhookLog:
    log = WebhookLog(
        shim_id=shim_id,
        received_at=now() - timedelta(days=days_ago),
        payload="{}",
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def _log_count(session: AsyncSession, shim_id: int) -> int:
    from sqlmodel import select, func

    result = await session.exec(
        select(func.count()).where(WebhookLog.shim_id == shim_id)
    )
    return result.one()


@pytest.mark.anyio
async def test_deletes_logs_outside_global_retention(session: AsyncSession):
    _app_config.update(log_retention_days=7)
    shim = await _make_shim(session, "s1")
    await _make_log(session, shim.id, days_ago=10)  # outside window
    await _make_log(session, shim.id, days_ago=3)  # inside window

    deleted = await delete_old_logs(session)

    assert deleted == 1
    assert await _log_count(session, shim.id) == 1


@pytest.mark.anyio
async def test_keeps_all_logs_when_retention_is_zero(session: AsyncSession):
    _app_config.update(log_retention_days=0)
    shim = await _make_shim(session, "s2")
    await _make_log(session, shim.id, days_ago=365)
    await _make_log(session, shim.id, days_ago=1)

    deleted = await delete_old_logs(session)

    assert deleted == 0
    assert await _log_count(session, shim.id) == 2


@pytest.mark.anyio
async def test_per_shim_retention_overrides_global(session: AsyncSession):
    _app_config.update(log_retention_days=30)
    shim = await _make_shim(session, "s3", retention=3)
    await _make_log(session, shim.id, days_ago=5)  # outside shim window
    await _make_log(session, shim.id, days_ago=1)  # inside shim window

    deleted = await delete_old_logs(session)

    assert deleted == 1
    assert await _log_count(session, shim.id) == 1


@pytest.mark.anyio
async def test_per_shim_retention_zero_keeps_all(session: AsyncSession):
    _app_config.update(log_retention_days=7)
    shim = await _make_shim(session, "s4", retention=0)
    await _make_log(session, shim.id, days_ago=365)

    deleted = await delete_old_logs(session)

    assert deleted == 0
    assert await _log_count(session, shim.id) == 1


@pytest.mark.anyio
async def test_groups_shims_by_retention(session: AsyncSession):
    """Two shims with different policies each get the right logs deleted."""
    _app_config.update(log_retention_days=30)
    shim_a = await _make_shim(session, "s5a", retention=7)
    shim_b = await _make_shim(session, "s5b", retention=14)

    await _make_log(session, shim_a.id, days_ago=10)  # outside 7d
    await _make_log(session, shim_a.id, days_ago=3)  # inside 7d
    await _make_log(session, shim_b.id, days_ago=20)  # outside 14d
    await _make_log(session, shim_b.id, days_ago=7)  # inside 14d

    deleted = await delete_old_logs(session)

    assert deleted == 2
    assert await _log_count(session, shim_a.id) == 1
    assert await _log_count(session, shim_b.id) == 1


@pytest.mark.anyio
async def test_no_shims_returns_zero(session: AsyncSession):
    deleted = await delete_old_logs(session)
    assert deleted == 0


@pytest.mark.anyio
async def test_returns_zero_when_nothing_to_delete(session: AsyncSession):
    _app_config.update(log_retention_days=30)
    shim = await _make_shim(session, "s6")
    await _make_log(session, shim.id, days_ago=1)

    deleted = await delete_old_logs(session)

    assert deleted == 0


@pytest.mark.anyio
async def test_does_not_delete_other_shims_logs(session: AsyncSession):
    """Retention on one shim must not affect another shim's logs."""
    _app_config.update(log_retention_days=30)
    shim_a = await _make_shim(session, "s7a", retention=7)
    shim_b = await _make_shim(session, "s7b")  # uses global 30d

    await _make_log(session, shim_a.id, days_ago=10)  # outside shim_a 7d window
    await _make_log(session, shim_b.id, days_ago=10)  # inside shim_b 30d window

    deleted = await delete_old_logs(session)

    assert deleted == 1
    assert await _log_count(session, shim_a.id) == 0
    assert await _log_count(session, shim_b.id) == 1
