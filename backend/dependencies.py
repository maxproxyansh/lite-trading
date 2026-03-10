from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models import AgentApiKey, Portfolio, User
from security import decode_access_token, hash_secret


settings = get_settings()


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    access_cookie: str | None = Cookie(default=None, alias=settings.access_cookie_name),
    csrf_cookie: str | None = Cookie(default=None, alias=settings.csrf_cookie_name),
    csrf_header: str | None = Header(default=None, alias=settings.csrf_header_name),
    db: Session = Depends(get_db),
) -> User:
    using_cookie_auth = False
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif access_cookie:
        token = access_cookie
        using_cookie_auth = True
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

    if using_cookie_auth and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")

    try:
        payload = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc
    user = db.query(User).filter(User.id == payload.get("sub"), User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_user_portfolio_ids(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    rows = db.query(Portfolio.id).filter(Portfolio.user_id == user.id).all()
    return [row[0] for row in rows]


def require_portfolio_access(
    portfolio_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> str:
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id, Portfolio.user_id == user.id).first()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return portfolio_id


def require_role(*allowed: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency


def get_refresh_cookie(
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
) -> str:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    return refresh_token


def get_agent_key(
    api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> AgentApiKey:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key")
    key = db.query(AgentApiKey).filter(
        AgentApiKey.key_hash == hash_secret(api_key),
        AgentApiKey.is_active.is_(True),
    ).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    if not key.user_id or not key.portfolio_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Legacy API key is no longer valid")
    key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return key


def require_agent_scope(*required: str) -> Callable:
    def dependency(key: AgentApiKey = Depends(get_agent_key)) -> AgentApiKey:
        scopes = set(key.scopes or [])
        if not all(scope in scopes for scope in required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient API key scopes")
        return key

    return dependency
