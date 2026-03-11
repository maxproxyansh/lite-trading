from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user, get_refresh_cookie, require_role
from rate_limit import rate_limit
from schemas import AgentKeyResponse, CreateAgentKeyRequest, CreateUserRequest, LoginRequest, SignupRequest, TokenEnvelope, UserSummary
from services.agent_service import serialize_agent_key
from services.auth_service import (
    authenticate_user,
    create_agent_key,
    create_user,
    issue_tokens,
    list_agent_keys,
    revoke_agent_key,
    revoke_refresh_token,
    rotate_refresh_token,
    signup_user,
)


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/auth", tags=["auth"])
admin_router = APIRouter(prefix=f"{settings.api_prefix}/admin", tags=["admin"])


def _cookie_secure() -> bool:
    return settings.refresh_cookie_secure or settings.app_env == "production"


def _cookie_samesite() -> str:
    if _cookie_secure():
        return "none"
    return settings.refresh_cookie_samesite


def _prepare_auth_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        max_age=settings.refresh_token_days * 24 * 60 * 60,
    )


def _set_access_cookie(response: Response, access_token: str, expires_in: int) -> None:
    response.set_cookie(
        key=settings.access_cookie_name,
        value=access_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        max_age=expires_in,
    )


def _set_csrf_cookie(response: Response, csrf_token: str, expires_in: int) -> None:
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        max_age=expires_in,
    )


@router.post("/signup", response_model=TokenEnvelope)
def signup(
    payload: SignupRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth:signup", 5, 60)),
):
    _prepare_auth_response(response)
    user = signup_user(db, payload)
    access_token, expires_in, refresh_token, csrf_token = issue_tokens(db, user)
    _set_access_cookie(response, access_token, expires_in)
    _set_refresh_cookie(response, refresh_token)
    _set_csrf_cookie(response, csrf_token, expires_in)
    return TokenEnvelope(access_token=access_token, expires_in=expires_in, user=UserSummary.model_validate(user))


@router.post("/login", response_model=TokenEnvelope)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth:login", 10, 60)),
):
    _prepare_auth_response(response)
    user = authenticate_user(db, payload.email, payload.password)
    access_token, expires_in, refresh_token, csrf_token = issue_tokens(db, user)
    _set_access_cookie(response, access_token, expires_in)
    _set_refresh_cookie(response, refresh_token)
    _set_csrf_cookie(response, csrf_token, expires_in)
    return TokenEnvelope(access_token=access_token, expires_in=expires_in, user=UserSummary.model_validate(user))


@router.post("/refresh", response_model=TokenEnvelope)
def refresh(
    response: Response,
    refresh_token: str = Depends(get_refresh_cookie),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth:refresh", 30, 60)),
):
    _prepare_auth_response(response)
    user, access_token, expires_in, next_refresh, csrf_token = rotate_refresh_token(db, refresh_token)
    _set_access_cookie(response, access_token, expires_in)
    _set_refresh_cookie(response, next_refresh)
    _set_csrf_cookie(response, csrf_token, expires_in)
    return TokenEnvelope(access_token=access_token, expires_in=expires_in, user=UserSummary.model_validate(user))


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Depends(get_refresh_cookie),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth:logout", 30, 60)),
):
    _prepare_auth_response(response)
    revoke_refresh_token(db, refresh_token)
    response.delete_cookie(settings.access_cookie_name, secure=_cookie_secure(), samesite=_cookie_samesite())
    response.delete_cookie(settings.refresh_cookie_name, secure=_cookie_secure(), samesite=_cookie_samesite())
    response.delete_cookie(settings.csrf_cookie_name, secure=_cookie_secure(), samesite=_cookie_samesite())
    return {"success": True}


@router.get("/me", response_model=UserSummary)
def me(user=Depends(get_current_user)):
    return UserSummary.model_validate(user)


@router.post("/api-keys", response_model=AgentKeyResponse)
def create_self_agent_key_route(
    payload: CreateAgentKeyRequest,
    db: Session = Depends(get_db),
    actor=Depends(require_role("admin", "trader")),
    _: None = Depends(rate_limit("auth:create-agent-key", 20, 60)),
):
    key, secret = create_agent_key(db, payload, actor)
    return serialize_agent_key(key, secret=secret)


@router.get("/api-keys", response_model=list[AgentKeyResponse])
def list_self_agent_keys_route(
    db: Session = Depends(get_db),
    actor=Depends(require_role("admin", "trader")),
):
    return [serialize_agent_key(key) for key in list_agent_keys(db, actor)]


@router.delete("/api-keys/{key_id}", response_model=AgentKeyResponse)
def revoke_self_agent_key_route(
    key_id: str,
    db: Session = Depends(get_db),
    actor=Depends(require_role("admin", "trader")),
    _: None = Depends(rate_limit("auth:revoke-agent-key", 20, 60)),
):
    return serialize_agent_key(revoke_agent_key(db, key_id, actor))


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
    return serialize_agent_key(key, secret=secret)
