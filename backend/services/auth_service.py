from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from models import AgentApiKey, Portfolio, RefreshToken, User
from schemas import CreateAgentKeyRequest, CreateUserRequest, SignupRequest, UserSummary
from security import (
    hash_password,
    hash_secret,
    key_prefix,
    make_access_token,
    make_agent_secret,
    make_csrf_token,
    make_refresh_token,
    password_needs_rehash,
    verify_password,
)
from services.audit import log_audit


settings = get_settings()
DEFAULT_AGENT_SCOPES = [
    "orders:read",
    "orders:write",
    "positions:read",
    "positions:write",
    "signals:read",
    "signals:write",
    "funds:read",
]
STARTING_CASH = 500_000.0
PORTFOLIO_KINDS = ("manual", "agent")


def _portfolio_kind(portfolio: Portfolio) -> str:
    if portfolio.kind in PORTFOLIO_KINDS:
        return portfolio.kind
    token = f"{portfolio.id} {portfolio.name or ''}".lower()
    return "agent" if "agent" in token else "manual"


def _portfolio_id(user: User, kind: str) -> str:
    return f"{kind}-{user.id[:8]}"


def _portfolio_name(user: User, kind: str) -> str:
    if kind == "agent":
        return f"{user.display_name} Agent"
    return f"{user.display_name} Manual"


def _portfolio_description(kind: str) -> str:
    if kind == "agent":
        return "Dedicated paper-trading portfolio for automated agents"
    return "Primary paper-trading portfolio for manual trading"


def ensure_user_portfolios(db: Session, user: User) -> dict[str, Portfolio]:
    portfolios = db.query(Portfolio).filter(Portfolio.user_id == user.id).order_by(Portfolio.created_at.asc()).all()
    existing_ids = {portfolio.id for portfolio in portfolios}
    by_kind: dict[str, Portfolio] = {}

    for portfolio in portfolios:
        kind = _portfolio_kind(portfolio)
        if portfolio.kind != kind:
            portfolio.kind = kind
        if kind not in by_kind:
            by_kind[kind] = portfolio

    for kind in PORTFOLIO_KINDS:
        if kind in by_kind:
            portfolio = by_kind[kind]
            if not portfolio.description:
                portfolio.description = _portfolio_description(kind)
            continue
        candidate_id = _portfolio_id(user, kind)
        suffix = 2
        while candidate_id in existing_ids:
            candidate_id = f"{_portfolio_id(user, kind)}-{suffix}"
            suffix += 1
        portfolio = Portfolio(
            id=candidate_id,
            user_id=user.id,
            kind=kind,
            name=_portfolio_name(user, kind),
            description=_portfolio_description(kind),
            starting_cash=STARTING_CASH,
            cash_balance=STARTING_CASH,
        )
        db.add(portfolio)
        db.flush()
        by_kind[kind] = portfolio
        existing_ids.add(candidate_id)

    return by_kind


def ensure_bootstrap_state(db: Session) -> User | None:
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return None

    user = db.query(User).filter(User.email == settings.bootstrap_admin_email).first()
    if not user:
        user = User(
            email=settings.bootstrap_admin_email,
            display_name=settings.bootstrap_admin_name,
            password_hash=hash_password(settings.bootstrap_admin_password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.flush()
        log_audit(
            db,
            actor_type="system",
            actor_id=None,
            action="bootstrap.user.created",
            entity_type="user",
            entity_id=user.id,
            details={"email": user.email},
        )
    else:
        user.display_name = settings.bootstrap_admin_name
        user.role = "admin"
        user.is_active = True
        if not verify_password(settings.bootstrap_admin_password, user.password_hash):
            user.password_hash = hash_password(settings.bootstrap_admin_password)
            log_audit(
                db,
                actor_type="system",
                actor_id=None,
                action="bootstrap.user.password_rotated",
                entity_type="user",
                entity_id=user.id,
                details={"email": user.email},
            )

    portfolios = ensure_user_portfolios(db, user)

    if settings.bootstrap_agent_key:
        key = db.query(AgentApiKey).filter(
            AgentApiKey.name == settings.bootstrap_agent_name,
            AgentApiKey.user_id == user.id,
        ).first()
        if not key:
            key = AgentApiKey(
                name=settings.bootstrap_agent_name,
                user_id=user.id,
                portfolio_id=portfolios["agent"].id,
                key_prefix=key_prefix(settings.bootstrap_agent_key),
                key_hash=hash_secret(settings.bootstrap_agent_key),
                scopes=DEFAULT_AGENT_SCOPES,
                is_active=True,
            )
            db.add(key)
            db.flush()
            log_audit(
                db,
                actor_type="system",
                actor_id=None,
                action="bootstrap.agent_key.created",
                entity_type="agent_api_key",
                entity_id=key.id,
                details={"name": key.name, "portfolio_id": portfolios["agent"].id},
            )
        else:
            key.user_id = user.id
            key.portfolio_id = portfolios["agent"].id
            key.scopes = DEFAULT_AGENT_SCOPES
            key.is_active = True
            if key.key_prefix != key_prefix(settings.bootstrap_agent_key) or key.key_hash != hash_secret(settings.bootstrap_agent_key):
                key.key_prefix = key_prefix(settings.bootstrap_agent_key)
                key.key_hash = hash_secret(settings.bootstrap_agent_key)

    db.commit()
    db.refresh(user)
    return user


def signup_user(db: Session, payload: SignupRequest) -> User:
    if not settings.allow_public_signup:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public signup is disabled")
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role="trader",
        is_active=True,
    )
    db.add(user)
    db.flush()
    ensure_user_portfolios(db, user)
    log_audit(
        db,
        actor_type="user",
        actor_id=user.id,
        action="user.signup",
        entity_type="user",
        entity_id=user.id,
        details={"email": payload.email},
    )
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, int, str, str]:
    access_token, expires_in = make_access_token(user.id, user.role)
    refresh_secret, refresh_expires = make_refresh_token()
    csrf_token = make_csrf_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_secret(refresh_secret),
            expires_at=refresh_expires,
        )
    )
    db.commit()
    return access_token, expires_in, refresh_secret, csrf_token


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[User, str, int, str, str]:
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
    csrf_token = make_csrf_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_secret(next_secret),
            expires_at=next_expires,
        )
    )
    db.commit()
    return user, access_token, expires_in, next_secret, csrf_token


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
    db.flush()
    ensure_user_portfolios(db, user)
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
    portfolio = db.query(Portfolio).filter(Portfolio.id == payload.portfolio_id, Portfolio.user_id == actor.id).first()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    secret = make_agent_secret()
    key = AgentApiKey(
        name=payload.name,
        user_id=actor.id,
        portfolio_id=portfolio.id,
        key_prefix=key_prefix(secret),
        key_hash=hash_secret(secret),
        scopes=payload.scopes or DEFAULT_AGENT_SCOPES,
        is_active=True,
    )
    db.add(key)
    db.flush()
    log_audit(
        db,
        actor_type="user",
        actor_id=actor.id,
        action="agent_key.create",
        entity_type="agent_api_key",
        entity_id=key.id,
        details={"name": payload.name, "scopes": payload.scopes, "portfolio_id": portfolio.id},
    )
    db.commit()
    db.refresh(key)
    return key, secret
