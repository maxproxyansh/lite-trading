from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import AgentEvent
from schemas import AgentEventEnvelope, AgentEventSource


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def serialize_agent_event(event: AgentEvent) -> AgentEventEnvelope:
    return AgentEventEnvelope(
        id=event.id,
        type=event.event_type,
        occurred_at=event.occurred_at,
        user_id=event.user_id,
        portfolio_id=event.portfolio_id,
        agent_key_id=event.agent_key_id,
        source=AgentEventSource(type=event.source_type, id=event.source_id),
        data=dict(event.payload or {}),
        claimed_at=event.claimed_at,
        claim_expires_at=event.claim_expires_at,
        acked_at=event.acked_at,
        created_at=event.created_at,
        updated_at=event.updated_at,
        last_error=event.last_error,
    )


def create_agent_event(
    db: Session,
    *,
    agent_key_id: str,
    user_id: str,
    portfolio_id: str,
    event_type: str,
    source_type: str,
    source_id: str,
    payload: dict,
    occurred_at: datetime | None = None,
) -> AgentEvent:
    event = AgentEvent(
        agent_key_id=agent_key_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        payload=payload,
        occurred_at=occurred_at or _utcnow(),
    )
    db.add(event)
    db.flush()
    return event


def claim_agent_events(
    db: Session,
    *,
    agent_key_id: str,
    limit: int,
    lease_seconds: int,
    event_types: list[str] | None = None,
) -> list[AgentEvent]:
    now = _utcnow()
    query = (
        db.query(AgentEvent)
        .filter(
            AgentEvent.agent_key_id == agent_key_id,
            AgentEvent.acked_at.is_(None),
            or_(AgentEvent.claim_expires_at.is_(None), AgentEvent.claim_expires_at <= now),
        )
        .order_by(AgentEvent.occurred_at.asc(), AgentEvent.created_at.asc())
    )
    if event_types:
        query = query.filter(AgentEvent.event_type.in_(event_types))

    events = query.limit(limit).all()
    if not events:
        return []

    lease_expiry = now + timedelta(seconds=lease_seconds)
    for event in events:
        event.claimed_at = now
        event.claim_expires_at = lease_expiry
    db.commit()
    for event in events:
        db.refresh(event)
    return events


def ack_agent_event(
    db: Session,
    *,
    agent_key_id: str,
    event_id: str,
) -> AgentEvent:
    event = (
        db.query(AgentEvent)
        .filter(AgentEvent.id == event_id, AgentEvent.agent_key_id == agent_key_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent event not found")

    now = _utcnow()
    event.acked_at = now
    event.claim_expires_at = None
    event.last_error = None
    db.commit()
    db.refresh(event)
    return event


def fail_agent_event(
    db: Session,
    *,
    agent_key_id: str,
    event_id: str,
    error: str,
    retry_delay_seconds: int = 0,
) -> AgentEvent:
    event = (
        db.query(AgentEvent)
        .filter(AgentEvent.id == event_id, AgentEvent.agent_key_id == agent_key_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent event not found")

    now = _utcnow()
    event.last_error = error
    event.claimed_at = now
    event.claim_expires_at = now + timedelta(seconds=retry_delay_seconds) if retry_delay_seconds > 0 else now
    db.commit()
    db.refresh(event)
    return event
