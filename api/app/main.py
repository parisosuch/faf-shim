import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app import app_config as _app_config
from app.cleanup import start_cleanup_loop
from app.db import init_db, AsyncSessionLocal, AppConfig
from app.logger import setup_logging, get_logger
from app.routers import auth, shims, webhooks
from app.routers import config as config_router

logger = get_logger(__name__)


class _DynamicCORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware that reads allowed origins from the in-memory config singleton."""

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        cfg = _app_config.get()
        allowed = "*" in cfg.cors_origins or (origin and origin in cfg.cors_origins)

        if origin and allowed:
            if request.method == "OPTIONS":
                return Response(
                    status_code=204,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Methods": "*",
                        "Access-Control-Allow-Headers": "*",
                        "Access-Control-Max-Age": "600",
                    },
                )
            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            return response

        return await call_next(request)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    logger.info("faf-shim starting up")
    await init_db()
    logger.info("database initialised")
    async with AsyncSessionLocal() as session:
        cfg = (await session.exec(select(AppConfig))).first()
        if cfg:
            _app_config.update(
                cors_origins=cfg.cors_origins_list(),
                log_retention_days=cfg.log_retention_days,
                max_body_size_kb=cfg.max_body_size_kb,
            )
    logger.info("app config loaded")
    cleanup_task = asyncio.create_task(start_cleanup_loop())
    logger.info("cleanup task started")
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("faf-shim shutting down")


app = FastAPI(
    title="faf-shim",
    description="API shim for configuring webhook integrations",
    lifespan=lifespan,
)

app.add_middleware(_DynamicCORSMiddleware)

app.include_router(auth.router)
app.include_router(config_router.router)
app.include_router(shims.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
