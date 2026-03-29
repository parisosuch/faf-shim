import os

os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-that-is-long-enough-for-hs256")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.main import app
from app.db import get_session
from app import cache, rate_limit
from app.auth import create_access_token, init_password
from app.config import settings

TEST_PASSWORD = "testpassword"


@pytest.fixture(autouse=True, scope="session")
def patch_settings():
    settings.admin_username = "admin"
    settings.admin_password = TEST_PASSWORD
    settings.admin_password_hash = None
    settings.jwt_secret = "test-secret-for-pytest-that-is-long-enough-for-hs256"
    init_password()


@pytest.fixture(name="session")
async def session_fixture():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(name="client")
async def client_fixture(session: AsyncSession):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    cache.clear()
    rate_limit.clear()


@pytest.fixture(name="auth_headers")
def auth_headers_fixture():
    token = create_access_token(settings.admin_username)
    return {"Authorization": f"Bearer {token}"}
