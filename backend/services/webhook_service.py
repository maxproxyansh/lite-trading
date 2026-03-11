from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from database import SessionLocal
from models import AgentApiKey, AgentWebhook, WebhookDelivery
from schemas import AgentWebhookCreateRequest
from services.audit import log_audit


settings = get_settings()
logger = logging.getLogger("lite.webhooks")
RETRY_DELAYS_SECONDS = (5, 30, 120)
DELIVERY_TIMEOUT_SECONDS = 10.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _signing_secret(webhook_id: str, secret_salt: str) -> str:
    digest = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        f"{webhook_id}:{secret_salt}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"whsec_{digest}"


def webhook_signature(payload: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={signature}"


def list_webhooks(db: Session, *, agent_key_id: str) -> list[AgentWebhook]:
    return (
        db.query(AgentWebhook)
        .filter(AgentWebhook.agent_key_id == agent_key_id, AgentWebhook.is_active.is_(True))
        .order_by(AgentWebhook.created_at.desc())
        .all()
    )


def create_webhook(
    db: Session,
    *,
    agent_key: AgentApiKey,
    payload: AgentWebhookCreateRequest,
) -> tuple[AgentWebhook, str]:
    existing = (
        db.query(AgentWebhook)
        .filter(AgentWebhook.agent_key_id == agent_key.id, AgentWebhook.is_active.is_(True))
        .count()
    )
    if existing >= 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WEBHOOK_LIMIT_REACHED")

    webhook = AgentWebhook(
        agent_key_id=agent_key.id,
        user_id=agent_key.user_id,
        portfolio_id=agent_key.portfolio_id,
        url=payload.url,
        events=list(payload.events),
        secret_salt=secrets.token_urlsafe(18),
        is_active=True,
    )
    db.add(webhook)
    db.flush()
    secret = _signing_secret(webhook.id, webhook.secret_salt)

    log_audit(
        db,
        actor_type="agent",
        actor_id=agent_key.id,
        action="webhook.created",
        entity_type="webhook",
        entity_id=webhook.id,
        details={"url": webhook.url, "events": list(webhook.events or []), "portfolio_id": webhook.portfolio_id},
    )
    db.commit()
    db.refresh(webhook)
    return webhook, secret


def delete_webhook(db: Session, *, agent_key_id: str, webhook_id: str) -> None:
    webhook = (
        db.query(AgentWebhook)
        .filter(
            AgentWebhook.id == webhook_id,
            AgentWebhook.agent_key_id == agent_key_id,
            AgentWebhook.is_active.is_(True),
        )
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    db.query(WebhookDelivery).filter(
        WebhookDelivery.webhook_id == webhook.id,
        WebhookDelivery.delivered_at.is_(None),
    ).delete(synchronize_session=False)
    webhook.is_active = False
    log_audit(
        db,
        actor_type="agent",
        actor_id=agent_key_id,
        action="webhook.deleted",
        entity_type="webhook",
        entity_id=webhook.id,
        details={"url": webhook.url, "portfolio_id": webhook.portfolio_id},
    )
    db.commit()


def enqueue_webhook_event(
    db: Session,
    *,
    portfolio_id: str | None,
    event_type: str,
    payload: dict,
) -> int:
    if not portfolio_id:
        return 0

    now = _utcnow()
    webhooks = (
        db.query(AgentWebhook)
        .join(AgentApiKey, AgentApiKey.id == AgentWebhook.agent_key_id)
        .filter(
            AgentWebhook.portfolio_id == portfolio_id,
            AgentWebhook.is_active.is_(True),
            AgentApiKey.is_active.is_(True),
            AgentApiKey.revoked_at.is_(None),
            (AgentApiKey.expires_at.is_(None) | (AgentApiKey.expires_at > now)),
        )
        .all()
    )

    created = 0
    for webhook in webhooks:
        if event_type not in set(webhook.events or []):
            continue
        db.add(
            WebhookDelivery(
                webhook_id=webhook.id,
                event_type=event_type,
                payload=payload,
                attempt_count=0,
                next_attempt_at=now,
            )
        )
        created += 1
    return created


async def _deliver(client: httpx.AsyncClient, webhook: AgentWebhook, delivery: WebhookDelivery) -> tuple[bool, str | None]:
    secret = _signing_secret(webhook.id, webhook.secret_salt)
    body = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "lite-webhook/1.0",
        "X-Webhook-Signature": webhook_signature(body, secret),
        "X-Webhook-Event": delivery.event_type,
    }
    try:
        response = await client.post(webhook.url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        return False, str(exc)
    if 200 <= response.status_code < 300:
        return True, None
    return False, f"Webhook returned {response.status_code}"


async def process_webhook_deliveries_once(*, now: datetime | None = None, limit: int = 25) -> int:
    current_time = now or _utcnow()
    processed = 0
    db = SessionLocal()
    try:
        deliveries = (
            db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.delivered_at.is_(None),
                WebhookDelivery.next_attempt_at.is_not(None),
                WebhookDelivery.next_attempt_at <= current_time,
            )
            .order_by(WebhookDelivery.next_attempt_at.asc(), WebhookDelivery.created_at.asc())
            .limit(limit)
            .all()
        )
        if not deliveries:
            return 0

        async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT_SECONDS, follow_redirects=False) as client:
            for delivery in deliveries:
                webhook = (
                    db.query(AgentWebhook)
                    .join(AgentApiKey, AgentApiKey.id == AgentWebhook.agent_key_id)
                    .filter(
                        AgentWebhook.id == delivery.webhook_id,
                        AgentWebhook.is_active.is_(True),
                        AgentApiKey.is_active.is_(True),
                        AgentApiKey.revoked_at.is_(None),
                        (AgentApiKey.expires_at.is_(None) | (AgentApiKey.expires_at > current_time)),
                    )
                    .first()
                )
                if not webhook:
                    db.delete(delivery)
                    db.commit()
                    processed += 1
                    continue

                delivery.attempt_count += 1
                success, error = await _deliver(client, webhook, delivery)
                if success:
                    delivery.delivered_at = current_time
                    delivery.next_attempt_at = None
                    delivery.last_error = None
                    webhook.last_delivery_at = current_time
                    webhook.last_error = None
                else:
                    delivery.last_error = error
                    webhook.last_failure_at = current_time
                    webhook.last_error = error
                    if delivery.attempt_count <= len(RETRY_DELAYS_SECONDS):
                        delay = RETRY_DELAYS_SECONDS[delivery.attempt_count - 1]
                        delivery.next_attempt_at = current_time + timedelta(seconds=delay)
                    else:
                        delivery.next_attempt_at = None
                db.commit()
                processed += 1
        return processed
    finally:
        db.close()


async def run_webhook_dispatcher(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await process_webhook_deliveries_once()
        except Exception:  # noqa: BLE001
            logger.exception("Webhook delivery cycle failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.0)
        except TimeoutError:
            continue
