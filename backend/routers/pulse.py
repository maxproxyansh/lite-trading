from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user
from models import AgentApiKey, Portfolio, PulseClaimToken, User
from schemas import PulseClaimRequest, PulseClaimResponse, PulseSetupResponse, PulseStatusResponse
from security import hash_secret, key_prefix, make_agent_secret
from services.auth_service import _normalize_scopes
from services.audit import log_audit

settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/agent/pulse", tags=["pulse"])

PULSE_KEY_NAME = "lite-pulse"
PULSE_SCOPES = ["events:read", "signals:read", "funds:read"]
CLAIM_TOKEN_TTL_MINUTES = 10
API_KEY_TTL_DAYS = 365


def _get_agent_portfolio(db: Session, user: User) -> Portfolio:
    portfolio = db.query(Portfolio).filter(
        Portfolio.user_id == user.id,
        Portfolio.kind == "agent",
    ).first()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent portfolio not found")
    return portfolio


def _revoke_pulse_key(db: Session, user: User, portfolio: Portfolio) -> None:
    now = datetime.now(timezone.utc)
    keys = db.query(AgentApiKey).filter(
        AgentApiKey.user_id == user.id,
        AgentApiKey.portfolio_id == portfolio.id,
        AgentApiKey.name == PULSE_KEY_NAME,
        AgentApiKey.is_active.is_(True),
    ).all()
    for key in keys:
        key.is_active = False
        key.revoked_at = now
        log_audit(
            db,
            actor_type="user",
            actor_id=user.id,
            action="agent_key.revoked",
            entity_type="agent_api_key",
            entity_id=key.id,
            details={"name": key.name, "reason": "pulse-rotated"},
        )


def _invalidate_unclaimed_tokens(db: Session, user_id: str) -> None:
    db.query(PulseClaimToken).filter(
        PulseClaimToken.user_id == user_id,
        PulseClaimToken.claimed.is_(False),
    ).update({"claimed": True})


@router.post("/setup", response_model=PulseSetupResponse)
def pulse_setup(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    portfolio = _get_agent_portfolio(db, user)

    # Revoke existing pulse key and invalidate unclaimed tokens
    _revoke_pulse_key(db, user, portfolio)
    _invalidate_unclaimed_tokens(db, user.id)

    # Create new API key
    now = datetime.now(timezone.utc)
    secret = make_agent_secret()
    api_key = AgentApiKey(
        name=PULSE_KEY_NAME,
        user_id=user.id,
        portfolio_id=portfolio.id,
        key_prefix=key_prefix(secret),
        key_hash=hash_secret(secret),
        scopes=_normalize_scopes(PULSE_SCOPES),
        is_active=True,
        expires_at=now + timedelta(days=API_KEY_TTL_DAYS),
    )
    db.add(api_key)
    db.flush()

    log_audit(
        db,
        actor_type="user",
        actor_id=user.id,
        action="agent_key.create",
        entity_type="agent_api_key",
        entity_id=api_key.id,
        details={"name": PULSE_KEY_NAME, "scopes": api_key.scopes, "portfolio_id": portfolio.id},
    )

    # Create claim token
    raw_token = secrets.token_urlsafe(32)
    claim = PulseClaimToken(
        user_id=user.id,
        api_key_id=api_key.id,
        token_hash=hash_secret(raw_token),
        api_secret=secret,
        expires_at=now + timedelta(minutes=CLAIM_TOKEN_TTL_MINUTES),
    )
    db.add(claim)
    db.commit()

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return PulseSetupResponse(
        claim_token=raw_token,
        apk_url=settings.pulse_apk_url,
        key_prefix=key_prefix(secret),
    )


@router.post("/claim", response_model=PulseClaimResponse)
def pulse_claim(
    payload: PulseClaimRequest,
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    token_h = hash_secret(payload.token)
    claim = db.query(PulseClaimToken).filter(PulseClaimToken.token_hash == token_h).first()

    if not claim:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid claim token")
    if claim.claimed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token already claimed")

    expires_at = claim.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    # Mark claimed and extract secret
    claim.claimed = True
    api_secret = claim.api_secret
    claim.api_secret = ""

    # Verify the associated key is still active
    api_key = db.query(AgentApiKey).filter(
        AgentApiKey.id == claim.api_key_id,
        AgentApiKey.is_active.is_(True),
    ).first()
    if not api_key:
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Associated API key is no longer active")

    db.commit()
    return PulseClaimResponse(api_key=api_secret)


@router.delete("/setup")
def pulse_disconnect(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    portfolio = _get_agent_portfolio(db, user)
    _revoke_pulse_key(db, user, portfolio)
    _invalidate_unclaimed_tokens(db, user.id)
    db.commit()
    return {"ok": True}


@router.get("/status", response_model=PulseStatusResponse)
def pulse_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    portfolio = _get_agent_portfolio(db, user)
    key = db.query(AgentApiKey).filter(
        AgentApiKey.user_id == user.id,
        AgentApiKey.portfolio_id == portfolio.id,
        AgentApiKey.name == PULSE_KEY_NAME,
        AgentApiKey.is_active.is_(True),
        AgentApiKey.revoked_at.is_(None),
    ).first()
    if not key:
        return PulseStatusResponse(connected=False)
    return PulseStatusResponse(
        connected=True,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
    )
