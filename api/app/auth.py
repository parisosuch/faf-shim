import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer = HTTPBearer()
_password_hash: str = ""


def init_password() -> str | None:
    """Resolve the admin password hash at startup.

    Priority:
      1. ADMIN_PASSWORD_HASH (legacy, pre-hashed)
      2. ADMIN_PASSWORD (plain text, hashed here)
      3. Auto-generated random password (logged to stdout)

    Returns the generated plain-text password if one was auto-generated, else None.
    """
    global _password_hash
    if settings.admin_password_hash:
        _password_hash = settings.admin_password_hash
        return None
    if settings.admin_password:
        _password_hash = bcrypt.hashpw(settings.admin_password.encode(), bcrypt.gensalt()).decode()
        return None
    generated = secrets.token_urlsafe(24)
    _password_hash = bcrypt.hashpw(generated.encode(), bcrypt.gensalt()).decode()
    return generated


def get_password_hash() -> str:
    return _password_hash


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


_auth_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("sub") != settings.admin_username:
            raise _auth_exc
        return payload
    except jwt.PyJWTError:
        raise _auth_exc


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> dict:
    return decode_token(credentials.credentials)
