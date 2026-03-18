from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import app_config as _app_config
from app.auth import require_auth
from app.db import get_session, AppConfig, AppConfigRead, AppConfigUpdate

router = APIRouter(
    prefix="/config", tags=["config"], dependencies=[Depends(require_auth)]
)


async def _get_or_create(session: AsyncSession) -> AppConfig:
    cfg = (await session.exec(select(AppConfig))).first()
    if not cfg:
        cfg = AppConfig()
        session.add(cfg)
        await session.commit()
        await session.refresh(cfg)
    return cfg


@router.get("/", response_model=AppConfigRead)
async def get_config(session: AsyncSession = Depends(get_session)):
    cfg = await _get_or_create(session)
    return AppConfigRead(
        cors_origins=cfg.cors_origins_list(),
        log_retention_days=cfg.log_retention_days,
        max_body_size_kb=cfg.max_body_size_kb,
        cleanup_interval_seconds=cfg.cleanup_interval_seconds,
    )


@router.patch("/", response_model=AppConfigRead)
async def update_config(
    body: AppConfigUpdate, session: AsyncSession = Depends(get_session)
):
    import json

    cfg = await _get_or_create(session)
    if body.cors_origins is not None:
        cfg.cors_origins = json.dumps(body.cors_origins)
    if body.log_retention_days is not None:
        cfg.log_retention_days = body.log_retention_days
    if body.max_body_size_kb is not None:
        cfg.max_body_size_kb = body.max_body_size_kb
    if body.cleanup_interval_seconds is not None:
        cfg.cleanup_interval_seconds = body.cleanup_interval_seconds
    session.add(cfg)
    await session.commit()
    await session.refresh(cfg)
    _app_config.update(
        cors_origins=cfg.cors_origins_list(),
        log_retention_days=cfg.log_retention_days,
        max_body_size_kb=cfg.max_body_size_kb,
        cleanup_interval_seconds=cfg.cleanup_interval_seconds,
    )
    return AppConfigRead(
        cors_origins=cfg.cors_origins_list(),
        log_retention_days=cfg.log_retention_days,
        max_body_size_kb=cfg.max_body_size_kb,
        cleanup_interval_seconds=cfg.cleanup_interval_seconds,
    )
