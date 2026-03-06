from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models import AgentApiKey, User
from security import decode_access_token, hash_secret


settings = get_settings()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc
    user = db.query(User).filter(User.id == payload.get("sub"), User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


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
