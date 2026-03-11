from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import Alert
from schemas import AlertCreateRequest
from services.audit import log_audit
from services.market_data import market_data_service
from services.webhook_service import enqueue_webhook_event


MONEY_PLACES = Decimal("0.01")


def _money(value: float | int | Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        raw = value
    else:
        raw = Decimal(str(value))
    return raw.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def _to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP))


def _market_price(symbol: str) -> float | None:
    if symbol == "NIFTY 50":
        spot = market_data_service.snapshot.get("spot")
        if spot is None:
            return None
        return float(spot)
    quote = market_data_service.get_quote(symbol)
    if not quote or quote.get("ltp") is None:
        return None
    return float(quote["ltp"])


def list_alerts(
    db: Session,
    *,
    user_id: str,
    portfolio_id: str | None = None,
    include_cancelled: bool = False,
) -> list[Alert]:
    query = db.query(Alert).filter(Alert.user_id == user_id)
    if portfolio_id is not None:
        query = query.filter(Alert.portfolio_id == portfolio_id)
    if not include_cancelled:
        query = query.filter(Alert.status != "CANCELLED")
    return query.order_by(Alert.status.asc(), Alert.created_at.asc()).all()


def create_alert(
    db: Session,
    *,
    user_id: str,
    payload: AlertCreateRequest,
    portfolio_id: str | None = None,
    actor_type: str = "user",
    actor_id: str | None = None,
) -> Alert:
    current_price = _market_price(payload.symbol)
    if current_price is None or current_price <= 0:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MARKET_DATA_UNAVAILABLE")

    direction = payload.direction or ("ABOVE" if payload.target_price >= current_price else "BELOW")
    alert = Alert(
        user_id=user_id,
        portfolio_id=portfolio_id,
        symbol=payload.symbol,
        target_price=_money(payload.target_price),
        direction=direction,
        status="ACTIVE",
        last_price=_money(current_price),
    )
    db.add(alert)
    db.flush()
    log_audit(
        db,
        actor_type=actor_type,
        actor_id=actor_id or user_id,
        action="alert.create",
        entity_type="alert",
        entity_id=alert.id,
        details={
            "symbol": alert.symbol,
            "target_price": float(alert.target_price),
            "direction": alert.direction,
            "portfolio_id": alert.portfolio_id,
        },
    )
    db.commit()
    db.refresh(alert)
    return alert


def cancel_alert(
    db: Session,
    *,
    user_id: str,
    alert_id: str,
    portfolio_id: str | None = None,
    actor_type: str = "user",
    actor_id: str | None = None,
) -> Alert:
    query = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user_id)
    if portfolio_id is not None:
        query = query.filter(Alert.portfolio_id == portfolio_id)
    alert = query.first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.status = "CANCELLED"
    log_audit(
        db,
        actor_type=actor_type,
        actor_id=actor_id or user_id,
        action="alert.cancel",
        entity_type="alert",
        entity_id=alert.id,
        details={"symbol": alert.symbol, "portfolio_id": alert.portfolio_id},
    )
    db.commit()
    db.refresh(alert)
    return alert


def sync_alerts(db: Session) -> int:
    triggered = 0
    alerts = db.query(Alert).filter(Alert.status == "ACTIVE").all()
    for alert in alerts:
        current_price = _market_price(alert.symbol)
        if current_price is None or current_price <= 0:
            continue
        alert.last_price = _money(current_price)
        target_price = float(alert.target_price)
        if alert.direction == "ABOVE" and current_price >= target_price:
            alert.status = "TRIGGERED"
            alert.triggered_at = datetime.now(timezone.utc)
            enqueue_webhook_event(
                db,
                portfolio_id=alert.portfolio_id,
                event_type="alert.triggered",
                payload={
                    "event": "alert.triggered",
                    "occurred_at": alert.triggered_at.isoformat(),
                    "portfolio_id": alert.portfolio_id,
                    "data": {
                        "alert_id": alert.id,
                        "symbol": alert.symbol,
                        "target_price": float(alert.target_price),
                        "direction": alert.direction,
                        "last_price": current_price,
                    },
                },
            )
            triggered += 1
        elif alert.direction == "BELOW" and current_price <= target_price:
            alert.status = "TRIGGERED"
            alert.triggered_at = datetime.now(timezone.utc)
            enqueue_webhook_event(
                db,
                portfolio_id=alert.portfolio_id,
                event_type="alert.triggered",
                payload={
                    "event": "alert.triggered",
                    "occurred_at": alert.triggered_at.isoformat(),
                    "portfolio_id": alert.portfolio_id,
                    "data": {
                        "alert_id": alert.id,
                        "symbol": alert.symbol,
                        "target_price": float(alert.target_price),
                        "direction": alert.direction,
                        "last_price": current_price,
                    },
                },
            )
            triggered += 1
    if alerts:
        db.commit()
    return triggered
