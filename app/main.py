from fastapi import FastAPI

from app.routers import shims, webhooks

app = FastAPI(
    title="faf-shim", description="API shim for configuring webhook integrations"
)

app.include_router(shims.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
