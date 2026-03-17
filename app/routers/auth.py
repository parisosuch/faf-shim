from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import create_access_token, require_auth, verify_password
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    if body.username != settings.admin_username or not verify_password(
        body.password, settings.admin_password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return TokenResponse(access_token=create_access_token(body.username))


@router.get("/me")
def me(payload: Annotated[dict, Depends(require_auth)]):
    return {"username": payload["sub"]}


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: Annotated[dict, Depends(require_auth)]):
    return TokenResponse(access_token=create_access_token(payload["sub"]))
