import os

# Must be set before app is imported so Settings() doesn't fail validation
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$placeholder.hash.for.test.init")
os.environ.setdefault(
    "JWT_SECRET", "test-secret-for-pytest-that-is-long-enough-for-hs256"
)

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db import get_session
from app.auth import create_access_token, hash_password
from app.config import settings

TEST_PASSWORD = "testpassword"


@pytest.fixture(autouse=True, scope="session")
def patch_settings():
    settings.admin_username = "admin"
    settings.admin_password_hash = hash_password(TEST_PASSWORD)
    settings.jwt_secret = "test-secret-for-pytest-that-is-long-enough-for-hs256"


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def auth_headers_fixture():
    token = create_access_token(settings.admin_username)
    return {"Authorization": f"Bearer {token}"}
