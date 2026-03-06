from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from models import AgentApiKey, Portfolio, RefreshToken, User
from schemas import CreateAgentKeyRequest, CreateUserRequest, UserSummary
from security import hash_password, hash_secret, key_prefix, make_access_token, make_agent_secret, make_refresh_token, verify_password
from services.audit import log_audit


settings = get_settings()
DEFAULT_AGENT_SCOPES = ["orders:write", "positions:read", "positions:write", "signals:read", "signals:write", "funds:read"]


def ensure_bootstrap_state(db: Session) -> None:
    admin = db.query(User).filter(User.email == settings.bootstrap_admin_email).first()
    legacy_admin = db.query(User).filter(User.email == "admin@lite.local").first()
    if legacy_admin and not admin:
        legacy_admin.email = settings.bootstrap_admin_email
        legacy_admin.display_name = legacy_admin.display_name or "Lite Admin"
        if not legacy_admin.password_hash:
            legacy_admin.password_hash = hash_password(settings.bootstrap_admin_password)
        legacy_admin.role = "admin"
        legacy_admin.is_active = True
        db.flush()
        admin = legacy_admin
    elif legacy_admin and admin and legacy_admin.id != admin.id:
        legacy_admin.is_active = False

    if not admin:
        admin = User(
            email=settings.bootstrap_admin_email,
            display_name="Lite Admin",
            password_hash=hash_password(settings.bootstrap_admin_password),
            role="admin",
            is_active=True,
        )
        db.add(admin)

    for portfolio_id, name in (("manual", "Manual Trader"), ("agent", "Agent Trader")):
        if not db.query(Portfolio).filter(Portfolio.id == portfolio_id).first():
            db.add(
                Portfolio(
                    id=portfolio_id,
                    name=name,
                    description=f"{name} virtual options portfolio",
                )
            )

    key_hash = hash_secret(settings.bootstrap_agent_key)
    existing_key = db.query(AgentApiKey).filter(AgentApiKey.key_hash == key_hash).first()
    if existing_key:
        current_scopes = set(existing_key.scopes or [])
        merged_scopes = sorted(current_scopes.union(DEFAULT_AGENT_SCOPES))
        if merged_scopes != list(existing_key.scopes or []):
            existing_key.scopes = merged_scopes
            existing_key.is_active = True
    else:
        db.add(
            AgentApiKey(
                name=settings.bootstrap_agent_name,
                key_prefix=key_prefix(settings.bootstrap_agent_key),
                key_hash=key_hash,
                scopes=DEFAULT_AGENT_SCOPES,
                is_active=True,
            )
        )

    db.commit()


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, int, str]:
    access_token, expires_in = make_access_token(user.id, user.role)
    refresh_secret, refresh_expires = make_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_secret(refresh_secret),
            expires_at=refresh_expires,
        )
    )
    db.commit()
    return access_token, expires_in, refresh_secret


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[User, str, int, str]:
    token_hash = hash_secret(raw_token)
    token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    now = datetime.now(timezone.utc)
    if not token or token.revoked_at or token.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.query(User).filter(User.id == token.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    token.revoked_at = now
    access_token, expires_in = make_access_token(user.id, user.role)
    next_secret, next_expires = make_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_secret(next_secret),
            expires_at=next_expires,
        )
    )
    db.commit()
    return user, access_token, expires_in, next_secret


def revoke_refresh_token(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    token = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_secret(raw_token)).first()
    if token and not token.revoked_at:
        token.revoked_at = datetime.now(timezone.utc)
        db.commit()


def create_user(db: Session, payload: CreateUserRequest, actor: User) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    log_audit(
        db,
        actor_type="user",
        actor_id=actor.id,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        details={"email": payload.email, "role": payload.role},
    )
    db.commit()
    db.refresh(user)
    return user


def create_agent_key(db: Session, payload: CreateAgentKeyRequest, actor: User) -> tuple[AgentApiKey, str]:
    secret = make_agent_secret()
    key = AgentApiKey(
        name=payload.name,
        key_prefix=key_prefix(secret),
        key_hash=hash_secret(secret),
        scopes=payload.scopes,
        is_active=True,
    )
    db.add(key)
    log_audit(
        db,
        actor_type="user",
        actor_id=actor.id,
        action="agent_key.create",
        entity_type="agent_api_key",
        entity_id=key.id,
        details={"name": payload.name, "scopes": payload.scopes},
    )
    db.commit()
    db.refresh(key)
    return key, secret
