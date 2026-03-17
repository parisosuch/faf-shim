from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db import init_db
from app.logger import setup_logging, get_logger
from app.routers import auth, shims, webhooks

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    logger.info("faf-shim starting up")
    init_db()
    logger.info("database initialised")
    yield
    logger.info("faf-shim shutting down")


app = FastAPI(
    title="faf-shim",
    description="API shim for configuring webhook integrations",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(shims.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
