from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user, get_refresh_cookie, require_role
from rate_limit import rate_limit
from schemas import AgentKeyResponse, CreateAgentKeyRequest, CreateUserRequest, LoginRequest, TokenEnvelope, UserSummary
from services.auth_service import authenticate_user, create_agent_key, create_user, issue_tokens, revoke_refresh_token, rotate_refresh_token


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/auth", tags=["auth"])
admin_router = APIRouter(prefix=f"{settings.api_prefix}/admin", tags=["admin"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
    )


@router.post("/login", response_model=TokenEnvelope)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth:login", 10, 60)),
):
    user = authenticate_user(db, payload.email, payload.password)
    access_token, expires_in, refresh_token = issue_tokens(db, user)
    _set_refresh_cookie(response, refresh_token)
    return TokenEnvelope(access_token=access_token, expires_in=expires_in, user=UserSummary.model_validate(user))


@router.post("/refresh", response_model=TokenEnvelope)
def refresh(
    response: Response,
    refresh_token: str = Depends(get_refresh_cookie),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth:refresh", 30, 60)),
):
    user, access_token, expires_in, next_refresh = rotate_refresh_token(db, refresh_token)
    _set_refresh_cookie(response, next_refresh)
    return TokenEnvelope(access_token=access_token, expires_in=expires_in, user=UserSummary.model_validate(user))


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Depends(get_refresh_cookie),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth:logout", 30, 60)),
):
    revoke_refresh_token(db, refresh_token)
    response.delete_cookie(settings.refresh_cookie_name)
    return {"success": True}


@router.get("/me", response_model=UserSummary)
def me(user=Depends(get_current_user)):
    return UserSummary.model_validate(user)


@admin_router.post("/users", response_model=UserSummary)
def create_user_route(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    actor=Depends(require_role("admin")),
    _: None = Depends(rate_limit("admin:create-user", 20, 60)),
):
    user = create_user(db, payload, actor)
    return UserSummary.model_validate(user)


@admin_router.post("/api-keys", response_model=AgentKeyResponse)
def create_agent_key_route(
    payload: CreateAgentKeyRequest,
    db: Session = Depends(get_db),
    actor=Depends(require_role("admin")),
    _: None = Depends(rate_limit("admin:create-agent-key", 20, 60)),
):
    key, secret = create_agent_key(db, payload, actor)
    return AgentKeyResponse(id=key.id, name=key.name, key_prefix=key.key_prefix, scopes=key.scopes, secret=secret)
