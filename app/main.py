from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db import init_db
from app.routers import auth, shims, webhooks


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


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
