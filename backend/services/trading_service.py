from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import market_hours
from config import get_settings
from models import Fill, Order, Portfolio, Position
from schemas import BracketOrderRequest, FundsResponse, OrderModifyRequest, OrderRequest
from services.audit import log_audit
from services.dhan_credential_service import DhanApiError, dhan_credential_service
from services.market_data import market_data_service
from services.webhook_service import enqueue_webhook_event


settings = get_settings()
LOT_SIZE = settings.nifty_lot_size
MONEY_PLACES = Decimal("0.01")


@dataclass
class QuoteContext:
    symbol: str
    security_id: str | None
    ltp: float
    bid: float | None
    ask: float | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _money(value: float | int | Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        raw = value
    else:
        raw = Decimal(str(value))
    return raw.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def _to_float(value: Decimal) -> float:
    return float(value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP))


def _dialect(db: Session) -> str:
    return db.bind.dialect.name if db.bind else ""


def _lock_query(query, db: Session, *, skip_locked: bool = False):
    if _dialect(db) == "postgresql":
        return query.with_for_update(skip_locked=skip_locked)
    return query


def _available_funds(portfolio: Portfolio) -> float:
    return _to_float(
        _money(portfolio.cash_balance)
        - _money(portfolio.blocked_margin)
        - _money(portfolio.blocked_premium)
    )


def _estimate_charges(price: float, quantity: int, side: str) -> float:
    turnover = _money(price) * Decimal(quantity)
    brokerage = min(turnover * Decimal("0.0003"), Decimal("20.00"))
    stt = turnover * (Decimal("0.0005") if side == "SELL" else Decimal("0"))
    exchange_txn = turnover * Decimal("0.00053")
    sebi = turnover * Decimal("0.000001")
    gst = (brokerage + exchange_txn) * Decimal("0.18")
    stamp = turnover * (Decimal("0.00003") if side == "BUY" else Decimal("0"))
    return _to_float(brokerage + stt + exchange_txn + sebi + gst + stamp)


def _fallback_short_margin(price: float, quantity: int) -> float:
    return _to_float(max(_money(price) * Decimal(quantity) * Decimal("2.5"), Decimal("25000.00")))


def _margin_from_dhan(security_id: str | None, side: str, quantity: int, price: float, product: str) -> float | None:
    snapshot = dhan_credential_service.snapshot()
    if side != "SELL" or not security_id or not snapshot.configured:
        return None
    try:
        payload = dhan_credential_service.call(
            "margin_calculator",
            lambda client: client.margin_calculator(
                security_id=security_id,
                exchange_segment="NSE_FNO",
                transaction_type=side,
                quantity=quantity,
                product_type="INTRA" if product == "MIS" else "MARGIN",
                price=price,
            ),
        )
    except DhanApiError:
        return None

    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    for key in ("total_margin", "totalMarginRequired", "margin_required", "required_margin", "margin"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if value is not None:
            try:
                return _to_float(_money(float(value)))
            except (TypeError, ValueError):
                continue
    return None


def _quote_context(order: OrderRequest) -> QuoteContext:
    symbol = order.symbol or market_data_service.resolve_symbol(
        expiry=order.expiry,
        strike=order.strike,
        option_type=order.option_type,
    )
    return _quote_context_for_symbol(symbol)


def _quote_context_for_symbol(symbol: str) -> QuoteContext:
    quote = market_data_service.get_quote(symbol)
    if not quote:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MARKET_DATA_UNAVAILABLE")
    return QuoteContext(
        symbol=symbol,
        security_id=quote.get("security_id"),
        ltp=float(quote.get("ltp") or 0.0),
        bid=quote.get("bid"),
        ask=quote.get("ask"),
    )


def _ensure_market_accepts_order_entry() -> None:
    rejection_reason = market_hours.order_entry_rejection_reason()
    if rejection_reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=rejection_reason)


def _validate_order_modification(order: Order, *, price: float | None, trigger_price: float | None, quantity: int) -> None:
    if quantity <= 0 or quantity % LOT_SIZE != 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Quantity must be a positive multiple of {LOT_SIZE}")

    if order.order_type == "LIMIT":
        if price is None or price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="LIMIT orders require price")
        if trigger_price is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="LIMIT orders do not support trigger_price")
    elif order.order_type == "SL":
        if price is None or price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SL orders require price")
        if trigger_price is None or trigger_price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SL orders require trigger_price")
    elif order.order_type == "SL-M":
        if trigger_price is None or trigger_price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SL-M orders require trigger_price")
        if price is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SL-M orders do not support price")
    elif order.order_type == "MARKET":
        if price is not None or trigger_price is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MARKET orders do not support price updates")


def _price_for_market(quote: QuoteContext, side: str) -> float:
    if side == "BUY":
        return float(quote.ask or quote.ltp or 0.0)
    return float(quote.bid or quote.ltp or 0.0)


def _should_fill(order_type: str, side: str, quote: QuoteContext, price: float | None, trigger_price: float | None) -> tuple[bool, str]:
    ltp = quote.ltp
    bid = quote.bid or ltp
    ask = quote.ask or ltp
    if order_type == "MARKET":
        return True, "FILLED"
    if order_type == "LIMIT":
        if side == "BUY" and price is not None and price >= ask:
            return True, "FILLED"
        if side == "SELL" and price is not None and price <= bid:
            return True, "FILLED"
        return False, "OPEN"
    if order_type == "SL":
        if side == "BUY" and trigger_price is not None and ltp >= trigger_price and price is not None and price >= ask:
            return True, "FILLED"
        if side == "SELL" and trigger_price is not None and ltp <= trigger_price and price is not None and price <= bid:
            return True, "FILLED"
        return False, "TRIGGER_PENDING"
    if order_type == "SL-M":
        if side == "BUY" and trigger_price is not None and ltp >= trigger_price:
            return True, "FILLED"
        if side == "SELL" and trigger_price is not None and ltp <= trigger_price:
            return True, "FILLED"
        return False, "TRIGGER_PENDING"
    return False, "REJECTED"


def _get_or_create_position(
    db: Session,
    *,
    portfolio_id: str,
    symbol: str,
    security_id: str | None,
    expiry: str,
    strike: int,
    option_type: str,
    product: str,
) -> Position:
    position = _lock_query(
        db.query(Position).filter(
            Position.portfolio_id == portfolio_id,
            Position.symbol == symbol,
            Position.product == product,
        ),
        db,
    ).first()
    if position:
        return position
    position = Position(
        portfolio_id=portfolio_id,
        symbol=symbol,
        security_id=security_id,
        expiry=expiry,
        strike=strike,
        option_type=option_type,
        product=product,
        net_quantity=0,
        lot_size=LOT_SIZE,
        average_open_price=0.0,
        last_price=0.0,
        blocked_margin=0.0,
        realized_pnl=0.0,
    )
    db.add(position)
    db.flush()
    return position


def _apply_fill_to_position(position: Position, side: str, quantity: int, price: float, margin_required: float) -> tuple[float, float]:
    realized_delta = 0.0
    released_margin = 0.0
    existing_qty = position.net_quantity
    price_money = _money(price)
    margin_money = _money(margin_required)

    if existing_qty == 0:
        position.net_quantity = quantity if side == "BUY" else -quantity
        position.average_open_price = _to_float(price_money)
        position.blocked_margin = _to_float(margin_money) if side == "SELL" else 0.0
        return realized_delta, released_margin

    if existing_qty > 0 and side == "BUY":
        total_cost = (_money(position.average_open_price) * Decimal(existing_qty)) + (price_money * Decimal(quantity))
        position.net_quantity = existing_qty + quantity
        position.average_open_price = _to_float(total_cost / Decimal(position.net_quantity))
        return realized_delta, released_margin

    if existing_qty < 0 and side == "SELL":
        current_abs = abs(existing_qty)
        total_credit = (_money(position.average_open_price) * Decimal(current_abs)) + (price_money * Decimal(quantity))
        position.net_quantity = -(current_abs + quantity)
        position.average_open_price = _to_float(total_credit / Decimal(abs(position.net_quantity)))
        position.blocked_margin = _to_float(_money(position.blocked_margin) + margin_money)
        return realized_delta, released_margin

    if existing_qty > 0 and side == "SELL":
        close_qty = min(existing_qty, quantity)
        realized_delta = _to_float((price_money - _money(position.average_open_price)) * Decimal(close_qty))
        remaining = quantity - close_qty
        position.net_quantity = existing_qty - close_qty
        if position.net_quantity == 0 and remaining == 0:
            position.average_open_price = 0.0
            position.blocked_margin = 0.0
            return realized_delta, released_margin
        if position.net_quantity > 0:
            return realized_delta, released_margin
        if remaining > 0:
            position.net_quantity = -remaining
            position.average_open_price = _to_float(price_money)
            position.blocked_margin = _to_float(margin_money)
        return realized_delta, released_margin

    if existing_qty < 0 and side == "BUY":
        short_abs = abs(existing_qty)
        close_qty = min(short_abs, quantity)
        realized_delta = _to_float((_money(position.average_open_price) - price_money) * Decimal(close_qty))
        release_ratio = close_qty / short_abs if short_abs else 0.0
        released_margin = _to_float(_money(position.blocked_margin) * Decimal(str(release_ratio)))
        position.blocked_margin = _to_float(max(_money(position.blocked_margin) - _money(released_margin), Decimal("0.00")))
        remaining = quantity - close_qty
        position.net_quantity = -(short_abs - close_qty)
        if position.net_quantity == 0 and remaining == 0:
            position.average_open_price = 0.0
            position.blocked_margin = 0.0
            return realized_delta, released_margin
        if position.net_quantity < 0:
            return realized_delta, released_margin
        if remaining > 0:
            position.net_quantity = remaining
            position.average_open_price = _to_float(price_money)
            position.blocked_margin = 0.0
        return realized_delta, released_margin

    return realized_delta, released_margin


def _refresh_position_mark(position: Position) -> None:
    quote = market_data_service.get_quote(position.symbol)
    if quote and quote.get("ltp") is not None:
        position.last_price = float(quote["ltp"])


def _active_status_for_order(order_type: str) -> str:
    return "TRIGGER_PENDING" if order_type in {"SL", "SL-M"} else "OPEN"


def _position_payload(position: Position, *, previous_quantity: int | None = None) -> dict[str, Any]:
    payload = {
        "position_id": position.id,
        "portfolio_id": position.portfolio_id,
        "symbol": position.symbol,
        "product": position.product,
        "expiry": position.expiry,
        "strike": position.strike,
        "option_type": position.option_type,
        "net_quantity": position.net_quantity,
        "average_open_price": float(position.average_open_price),
        "last_price": float(position.last_price),
        "blocked_margin": float(position.blocked_margin),
        "realized_pnl": float(position.realized_pnl),
    }
    if previous_quantity is not None:
        payload["previous_quantity"] = previous_quantity
    return payload


def _queue_position_events(db: Session, *, position: Position, previous_quantity: int, occurred_at: datetime) -> None:
    previous_sign = 0 if previous_quantity == 0 else (1 if previous_quantity > 0 else -1)
    current_sign = 0 if position.net_quantity == 0 else (1 if position.net_quantity > 0 else -1)

    if previous_sign == 0 and current_sign != 0:
        enqueue_webhook_event(
            db,
            portfolio_id=position.portfolio_id,
            event_type="position.opened",
            payload={
                "event": "position.opened",
                "occurred_at": occurred_at.isoformat(),
                "portfolio_id": position.portfolio_id,
                "data": _position_payload(position),
            },
        )
        return

    if previous_sign != 0 and current_sign == 0:
        enqueue_webhook_event(
            db,
            portfolio_id=position.portfolio_id,
            event_type="position.closed",
            payload={
                "event": "position.closed",
                "occurred_at": occurred_at.isoformat(),
                "portfolio_id": position.portfolio_id,
                "data": _position_payload(position, previous_quantity=previous_quantity),
            },
        )
        return

    if previous_sign != 0 and current_sign != 0 and previous_sign != current_sign:
        enqueue_webhook_event(
            db,
            portfolio_id=position.portfolio_id,
            event_type="position.closed",
            payload={
                "event": "position.closed",
                "occurred_at": occurred_at.isoformat(),
                "portfolio_id": position.portfolio_id,
                "data": _position_payload(position, previous_quantity=previous_quantity),
            },
        )
        enqueue_webhook_event(
            db,
            portfolio_id=position.portfolio_id,
            event_type="position.opened",
            payload={
                "event": "position.opened",
                "occurred_at": occurred_at.isoformat(),
                "portfolio_id": position.portfolio_id,
                "data": _position_payload(position),
            },
        )


def _estimate_order_requirements(
    *,
    order: Order,
    quote: QuoteContext,
    existing_qty: int,
) -> tuple[float, float, float, float]:
    reference_price = (
        float(order.price)
        if order.order_type in {"LIMIT", "SL"} and order.price is not None
        else _price_for_market(quote, order.side)
    )
    charges = _estimate_charges(reference_price, order.quantity, order.side)
    premium_required = _to_float(_money(reference_price) * Decimal(order.quantity)) if order.side == "BUY" else 0.0
    opening_short_quantity = 0
    if order.side == "SELL":
        if existing_qty > 0:
            opening_short_quantity = max(order.quantity - existing_qty, 0)
        else:
            opening_short_quantity = order.quantity
    margin_required = 0.0
    if opening_short_quantity > 0:
        margin_required = _margin_from_dhan(
            quote.security_id,
            order.side,
            opening_short_quantity,
            reference_price,
            order.product,
        )
        if margin_required is None:
            margin_required = _fallback_short_margin(reference_price, opening_short_quantity)
    return reference_price, charges, premium_required, margin_required


def _cancel_order_record(
    db: Session,
    order: Order,
    *,
    actor_type: str,
    actor_id: str | None,
    message: str,
) -> None:
    portfolio = _lock_query(db.query(Portfolio).filter(Portfolio.id == order.portfolio_id), db).first()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    if order.side == "BUY" and order.premium_required:
        portfolio.blocked_premium = _to_float(max(_money(portfolio.blocked_premium) - _money(order.premium_required), Decimal("0.00")))
    if order.side == "SELL" and order.margin_required:
        portfolio.blocked_margin = _to_float(max(_money(portfolio.blocked_margin) - _money(order.margin_required), Decimal("0.00")))

    order.status = "CANCELLED"
    order.message = message
    order.updated_at = _utcnow()

    log_audit(
        db,
        actor_type=actor_type,
        actor_id=actor_id,
        action="order.cancelled",
        entity_type="order",
        entity_id=order.id,
        details={"symbol": order.symbol, "portfolio_id": order.portfolio_id, "reason": message},
    )
    enqueue_webhook_event(
        db,
        portfolio_id=order.portfolio_id,
        event_type="order.cancelled",
        payload={
            "event": "order.cancelled",
            "occurred_at": order.updated_at.isoformat(),
            "portfolio_id": order.portfolio_id,
            "data": {
                "order_id": order.id,
                "symbol": order.symbol,
                "status": order.status,
                "side": order.side,
                "quantity": order.quantity,
                "product": order.product,
                "source": order.source,
                "parent_order_id": order.parent_order_id,
                "link_type": order.link_type,
            },
        },
    )


def _cancel_linked_siblings(db: Session, order: Order, *, actor_type: str, actor_id: str | None) -> None:
    if not order.parent_order_id:
        return
    siblings = (
        db.query(Order)
        .filter(
            Order.parent_order_id == order.parent_order_id,
            Order.id != order.id,
            Order.status.in_(("PARKED", "OPEN", "TRIGGER_PENDING")),
        )
        .all()
    )
    for sibling in siblings:
        _cancel_order_record(
            db,
            sibling,
            actor_type=actor_type,
            actor_id=actor_id,
            message="Cancelled by OCO sibling fill",
        )


def _activate_bracket_children(db: Session, parent: Order, *, actor_type: str, actor_id: str | None) -> None:
    children = (
        db.query(Order)
        .filter(Order.parent_order_id == parent.id, Order.status == "PARKED")
        .order_by(Order.created_at.asc())
        .all()
    )
    if not children:
        return

    portfolio = _lock_query(db.query(Portfolio).filter(Portfolio.id == parent.portfolio_id), db).first()
    position = _lock_query(
        db.query(Position).filter(
            Position.portfolio_id == parent.portfolio_id,
            Position.symbol == parent.symbol,
            Position.product == parent.product,
        ),
        db,
    ).first()
    if not portfolio or not position or position.net_quantity == 0:
        for child in children:
            _cancel_order_record(
                db,
                child,
                actor_type=actor_type,
                actor_id=actor_id,
                message="Bracket entry is not open",
            )
        return

    for child in children:
        if child.status != "PARKED":
            continue
        child.quantity = min(child.quantity, abs(position.net_quantity))
        child.lots = max(child.quantity // position.lot_size, 1)
        quote = _quote_context_for_symbol(child.symbol)
        reference_price, charges, premium_required, margin_required = _estimate_order_requirements(
            order=child,
            quote=quote,
            existing_qty=position.net_quantity,
        )
        should_fill, next_status = _should_fill(
            child.order_type,
            child.side,
            quote,
            float(child.price) if child.price is not None else None,
            float(child.trigger_price) if child.trigger_price is not None else None,
        )

        if child.side == "BUY":
            portfolio.blocked_premium = _to_float(_money(portfolio.blocked_premium) + _money(premium_required))
        else:
            portfolio.blocked_margin = _to_float(_money(portfolio.blocked_margin) + _money(margin_required))

        child.last_price = quote.ltp
        child.charges = charges
        child.premium_required = premium_required
        child.margin_required = margin_required
        child.updated_at = _utcnow()
        child.message = None

        log_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="order.activated",
            entity_type="order",
            entity_id=child.id,
            details={"symbol": child.symbol, "parent_order_id": parent.id, "link_type": child.link_type},
        )

        if should_fill:
            child.status = _active_status_for_order(child.order_type)
            _fill_order(
                db,
                child,
                fill_price=_price_for_market(quote, child.side) if child.order_type in {"MARKET", "SL-M"} else reference_price,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        else:
            child.status = next_status

def _position_unrealized(position: Position) -> float:
    if position.net_quantity == 0:
        return 0.0
    if position.net_quantity > 0:
        return _to_float((_money(position.last_price) - _money(position.average_open_price)) * Decimal(position.net_quantity))
    return _to_float((_money(position.average_open_price) - _money(position.last_price)) * Decimal(abs(position.net_quantity)))


def place_order(
    db: Session,
    payload: OrderRequest,
    *,
    actor_type: str,
    actor_id: str | None,
    source: str,
    quantity_override: int | None = None,
    auto_commit: bool = True,
) -> Order:
    try:
        if payload.idempotency_key:
            existing = _lock_query(db.query(Order).filter(Order.idempotency_key == payload.idempotency_key), db).first()
            if existing:
                return existing

        _ensure_market_accepts_order_entry()

        portfolio = _lock_query(db.query(Portfolio).filter(Portfolio.id == payload.portfolio_id), db).first()
        if not portfolio:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

        quote = _quote_context(payload)
        if quote.ltp <= 0:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MARKET_DATA_UNAVAILABLE")

        quantity = quantity_override or (payload.lots * LOT_SIZE)
        existing_position = _lock_query(
            db.query(Position).filter(
                Position.portfolio_id == payload.portfolio_id,
                Position.symbol == quote.symbol,
                Position.product == payload.product,
            ),
            db,
        ).first()
        existing_qty = existing_position.net_quantity if existing_position else 0
        reference_price = payload.price if payload.order_type in {"LIMIT", "SL"} and payload.price else _price_for_market(quote, payload.side)
        charges = _estimate_charges(reference_price, quantity, payload.side)
        premium_required = _to_float(_money(reference_price) * Decimal(quantity)) if payload.side == "BUY" else 0.0
        opening_short_quantity = 0
        if payload.side == "SELL":
            if existing_qty > 0:
                opening_short_quantity = max(quantity - existing_qty, 0)
            else:
                opening_short_quantity = quantity
        margin_required = 0.0
        if opening_short_quantity > 0:
            margin_required = _margin_from_dhan(quote.security_id, payload.side, opening_short_quantity, reference_price, payload.product)
            if margin_required is None:
                margin_required = _fallback_short_margin(reference_price, opening_short_quantity)

        required_funds = _money(premium_required) + _money(margin_required) + _money(charges)
        if _money(_available_funds(portfolio)) < required_funds:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INSUFFICIENT_FUNDS")

        should_fill, initial_status = _should_fill(payload.order_type, payload.side, quote, payload.price, payload.trigger_price)
        order = Order(
            portfolio_id=payload.portfolio_id,
            symbol=quote.symbol,
            security_id=quote.security_id,
            expiry=payload.expiry,
            strike=payload.strike,
            option_type=payload.option_type,
            side=payload.side,
            order_type=payload.order_type,
            product=payload.product,
            validity=payload.validity,
            lots=max(quantity // LOT_SIZE, 1),
            quantity=quantity,
            price=payload.price,
            trigger_price=payload.trigger_price,
            status=initial_status,
            last_price=quote.ltp,
            premium_required=premium_required,
            margin_required=margin_required or 0.0,
            charges=charges,
            signal_id=payload.signal_id,
            source=source,
            idempotency_key=payload.idempotency_key,
        )
        db.add(order)
        db.flush()

        if not should_fill:
            if payload.side == "BUY":
                portfolio.blocked_premium = _to_float(_money(portfolio.blocked_premium) + _money(premium_required))
            else:
                portfolio.blocked_margin = _to_float(_money(portfolio.blocked_margin) + _money(margin_required or 0.0))
            log_audit(
                db,
                actor_type=actor_type,
                actor_id=actor_id,
                action="order.placed",
                entity_type="order",
                entity_id=order.id,
                    details={"status": order.status, "symbol": order.symbol},
                )
            if auto_commit:
                db.commit()
                db.refresh(order)
            else:
                db.flush()
            return order

        _fill_order(
            db,
            order,
            fill_price=_price_for_market(quote, payload.side) if payload.order_type in {"MARKET", "SL-M"} else reference_price,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        if auto_commit:
            db.commit()
            db.refresh(order)
        else:
            db.flush()
        return order
    except IntegrityError as exc:
        db.rollback()
        if payload.idempotency_key:
            existing = db.query(Order).filter(Order.idempotency_key == payload.idempotency_key).first()
            if existing:
                return existing
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ORDER_CONFLICT") from exc


def _fill_order(db: Session, order: Order, *, fill_price: float, actor_type: str, actor_id: str | None) -> None:
    portfolio = _lock_query(db.query(Portfolio).filter(Portfolio.id == order.portfolio_id), db).first()
    was_pending = order.status in {"OPEN", "TRIGGER_PENDING"}
    position = _get_or_create_position(
        db,
        portfolio_id=order.portfolio_id,
        symbol=order.symbol,
        security_id=order.security_id,
        expiry=order.expiry,
        strike=order.strike,
        option_type=order.option_type,
        product=order.product,
    )
    previous_quantity = position.net_quantity
    if order.parent_order_id and order.link_type in {"STOP_LOSS", "TARGET"}:
        if previous_quantity == 0:
            _cancel_order_record(
                db,
                order,
                actor_type=actor_type,
                actor_id=actor_id,
                message="Bracket position is already closed",
            )
            return
        if abs(previous_quantity) < order.quantity:
            order.quantity = abs(previous_quantity)
            order.lots = max(order.quantity // position.lot_size, 1)

    if was_pending and order.side == "BUY":
        portfolio.blocked_premium = _to_float(max(_money(portfolio.blocked_premium) - _money(order.premium_required), Decimal("0.00")))

    realized_delta, released_margin = _apply_fill_to_position(position, order.side, order.quantity, fill_price, order.margin_required)
    position.realized_pnl = _to_float(_money(position.realized_pnl) + _money(realized_delta))
    position.last_price = _to_float(_money(fill_price))
    portfolio.realized_pnl = _to_float(_money(portfolio.realized_pnl) + _money(realized_delta))

    if order.side == "BUY":
        portfolio.cash_balance = _to_float(
            _money(portfolio.cash_balance) - (_money(fill_price) * Decimal(order.quantity)) - _money(order.charges)
        )
        if released_margin:
            portfolio.blocked_margin = _to_float(max(_money(portfolio.blocked_margin) - _money(released_margin), Decimal("0.00")))
    else:
        portfolio.cash_balance = _to_float(
            _money(portfolio.cash_balance) + (_money(fill_price) * Decimal(order.quantity)) - _money(order.charges)
        )
        if not was_pending and order.margin_required:
            portfolio.blocked_margin = _to_float(_money(portfolio.blocked_margin) + _money(order.margin_required))

    order.status = "FILLED"
    order.average_price = _to_float(_money(fill_price))
    order.filled_quantity = order.quantity
    order.filled_at = _utcnow()
    order.updated_at = _utcnow()

    snapshot = market_data_service.snapshot
    spot_at_fill = snapshot.get("spot") or None
    vix_at_fill = snapshot.get("vix") or None
    # Zero spot means no data loaded yet — treat as None
    if spot_at_fill is not None and float(spot_at_fill) == 0.0:
        spot_at_fill = None

    fill = Fill(
        order_id=order.id,
        portfolio_id=order.portfolio_id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=fill_price,
        charges=order.charges,
        spot_at_fill=spot_at_fill,
        vix_at_fill=vix_at_fill,
    )
    db.add(fill)

    log_audit(
        db,
        actor_type=actor_type,
        actor_id=actor_id,
        action="order.filled",
        entity_type="order",
        entity_id=order.id,
        details={"symbol": order.symbol, "price": fill_price, "quantity": order.quantity},
    )
    enqueue_webhook_event(
        db,
        portfolio_id=order.portfolio_id,
        event_type="order.filled",
        payload={
            "event": "order.filled",
            "occurred_at": (order.filled_at or _utcnow()).isoformat(),
            "portfolio_id": order.portfolio_id,
            "data": {
                "order_id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "status": order.status,
                "quantity": order.quantity,
                "average_price": float(order.average_price) if order.average_price is not None else None,
                "filled_quantity": order.filled_quantity,
                "product": order.product,
                "source": order.source,
                "parent_order_id": order.parent_order_id,
                "link_type": order.link_type,
            },
        },
    )
    _queue_position_events(
        db,
        position=position,
        previous_quantity=previous_quantity,
        occurred_at=order.filled_at or _utcnow(),
    )
    if order.link_type == "ENTRY":
        _activate_bracket_children(db, order, actor_type=actor_type, actor_id=actor_id)
    elif order.parent_order_id and order.link_type in {"STOP_LOSS", "TARGET"}:
        _cancel_linked_siblings(db, order, actor_type=actor_type, actor_id=actor_id)


async def process_open_orders() -> None:
    return None


def process_open_orders_sync(db: Session, symbols: set[str] | None = None) -> set[str]:
    changed_portfolios: set[str] = set()
    if not market_hours.is_market_open():
        return changed_portfolios
    mutated = False
    query = (
        db.query(Order)
        .filter(Order.status.in_(("OPEN", "TRIGGER_PENDING")))
        .order_by(Order.requested_at.asc())
    )
    if symbols:
        query = query.filter(Order.symbol.in_(sorted(symbols)))
    open_orders = _lock_query(query, db, skip_locked=True).all()
    for order in open_orders:
        quote_data = market_data_service.get_quote(order.symbol)
        if not quote_data:
            continue
        quote = QuoteContext(
            symbol=order.symbol,
            security_id=quote_data.get("security_id"),
            ltp=float(quote_data.get("ltp") or 0.0),
            bid=quote_data.get("bid"),
            ask=quote_data.get("ask"),
        )
        should_fill, next_status = _should_fill(order.order_type, order.side, quote, order.price, order.trigger_price)
        if should_fill:
            _fill_order(
                db,
                order,
                fill_price=_price_for_market(quote, order.side) if order.order_type in {"MARKET", "SL-M"} else float(order.price or quote.ltp),
                actor_type="system",
                actor_id=None,
            )
            mutated = True
            changed_portfolios.add(order.portfolio_id)
        else:
            if order.status != next_status:
                mutated = True
                order.status = next_status
                order.last_price = quote.ltp
                changed_portfolios.add(order.portfolio_id)
    if mutated:
        db.commit()
    return changed_portfolios


def list_orders(db: Session, portfolio_id: str | None = None) -> list[Order]:
    query = db.query(Order).order_by(Order.requested_at.desc())
    if portfolio_id:
        query = query.filter(Order.portfolio_id == portfolio_id)
    return query.all()


def search_orders(
    db: Session,
    *,
    portfolio_id: str,
    statuses: list[str] | None = None,
    symbol: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    offset: int = 0,
    limit: int = 50,
    sort: str = "desc",
) -> tuple[list[Order], int]:
    query = db.query(Order).filter(Order.portfolio_id == portfolio_id)
    if statuses:
        query = query.filter(Order.status.in_(statuses))
    if symbol:
        query = query.filter(Order.symbol.ilike(f"%{symbol}%"))
    if created_from is not None:
        start = datetime.combine(created_from, time.min, tzinfo=timezone.utc)
        query = query.filter(Order.created_at >= start)
    if created_to is not None:
        end = datetime.combine(created_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        query = query.filter(Order.created_at < end)

    total = query.count()
    ordering = Order.created_at.asc() if sort == "asc" else Order.created_at.desc()
    items = query.order_by(ordering, Order.id.asc()).offset(offset).limit(limit).all()
    return items, total


def get_order(db: Session, order_id: str, *, portfolio_id: str | None = None) -> Order:
    query = db.query(Order).filter(Order.id == order_id)
    if portfolio_id:
        query = query.filter(Order.portfolio_id == portfolio_id)
    order = query.first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def cancel_order(
    db: Session,
    order_id: str,
    *,
    portfolio_id: str | None = None,
    actor_type: str,
    actor_id: str | None,
) -> Order:
    order = _lock_query(db.query(Order).filter(Order.id == order_id), db).first()
    if not order or (portfolio_id and order.portfolio_id != portfolio_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status not in {"OPEN", "TRIGGER_PENDING", "PARKED"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ORDER_NOT_CANCELLABLE")

    _cancel_order_record(
        db,
        order,
        actor_type=actor_type,
        actor_id=actor_id,
        message="Order cancelled",
    )
    if order.parent_order_id is None:
        children = (
            db.query(Order)
            .filter(Order.parent_order_id == order.id, Order.status.in_(("PARKED", "OPEN", "TRIGGER_PENDING")))
            .all()
        )
        for child in children:
            _cancel_order_record(
                db,
                child,
                actor_type=actor_type,
                actor_id=actor_id,
                message="Parent order cancelled",
            )
    db.commit()
    db.refresh(order)
    return order


def modify_order(
    db: Session,
    order_id: str,
    payload: OrderModifyRequest,
    *,
    portfolio_id: str | None = None,
    actor_type: str,
    actor_id: str | None,
) -> Order:
    order = _lock_query(db.query(Order).filter(Order.id == order_id), db).first()
    if not order or (portfolio_id and order.portfolio_id != portfolio_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status not in {"OPEN", "TRIGGER_PENDING"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ORDER_NOT_MODIFIABLE")

    _ensure_market_accepts_order_entry()

    portfolio = _lock_query(db.query(Portfolio).filter(Portfolio.id == order.portfolio_id), db).first()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    quantity = payload.quantity or order.quantity
    price = payload.price if payload.price is not None else (float(order.price) if order.price is not None else None)
    trigger_price = (
        payload.trigger_price
        if payload.trigger_price is not None
        else (float(order.trigger_price) if order.trigger_price is not None else None)
    )
    _validate_order_modification(order, price=price, trigger_price=trigger_price, quantity=quantity)

    quote = _quote_context_for_symbol(order.symbol)
    existing_position = _lock_query(
        db.query(Position).filter(
            Position.portfolio_id == order.portfolio_id,
            Position.symbol == order.symbol,
            Position.product == order.product,
        ),
        db,
    ).first()
    existing_qty = existing_position.net_quantity if existing_position else 0
    reference_price = price if order.order_type in {"LIMIT", "SL"} and price is not None else _price_for_market(quote, order.side)
    charges = _estimate_charges(reference_price, quantity, order.side)
    premium_required = _to_float(_money(reference_price) * Decimal(quantity)) if order.side == "BUY" else 0.0
    opening_short_quantity = 0
    if order.side == "SELL":
        if existing_qty > 0:
            opening_short_quantity = max(quantity - existing_qty, 0)
        else:
            opening_short_quantity = quantity
    margin_required = 0.0
    if opening_short_quantity > 0:
        margin_required = _margin_from_dhan(quote.security_id, order.side, opening_short_quantity, reference_price, order.product)
        if margin_required is None:
            margin_required = _fallback_short_margin(reference_price, opening_short_quantity)

    available_after_release = _money(_available_funds(portfolio))
    if order.side == "BUY":
        available_after_release += _money(order.premium_required)
    else:
        available_after_release += _money(order.margin_required)

    required_funds = _money(premium_required) + _money(margin_required) + _money(charges)
    if available_after_release < required_funds:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INSUFFICIENT_FUNDS")

    should_fill, next_status = _should_fill(order.order_type, order.side, quote, price, trigger_price)

    if order.side == "BUY":
        portfolio.blocked_premium = _to_float(
            max(
                _money(portfolio.blocked_premium) - _money(order.premium_required) + _money(premium_required),
                Decimal("0.00"),
            )
        )
    else:
        portfolio.blocked_margin = _to_float(
            max(
                _money(portfolio.blocked_margin) - _money(order.margin_required) + _money(margin_required),
                Decimal("0.00"),
            )
        )

    old_state = {
        "price": float(order.price) if order.price is not None else None,
        "trigger_price": float(order.trigger_price) if order.trigger_price is not None else None,
        "quantity": order.quantity,
    }
    order.price = price
    order.trigger_price = trigger_price
    order.quantity = quantity
    order.lots = max(quantity // LOT_SIZE, 1)
    order.last_price = quote.ltp
    order.charges = charges
    order.premium_required = premium_required
    order.margin_required = margin_required or 0.0
    order.updated_at = _utcnow()
    order.message = None

    log_audit(
        db,
        actor_type=actor_type,
        actor_id=actor_id,
        action="order.modified",
        entity_type="order",
        entity_id=order.id,
        details={
            "symbol": order.symbol,
            "previous": old_state,
            "current": {"price": price, "trigger_price": trigger_price, "quantity": quantity},
        },
    )

    if should_fill:
        _fill_order(
            db,
            order,
            fill_price=_price_for_market(quote, order.side) if order.order_type in {"MARKET", "SL-M"} else reference_price,
            actor_type=actor_type,
            actor_id=actor_id,
        )
    else:
        order.status = next_status

    db.commit()
    db.refresh(order)
    return order


def list_linked_orders(db: Session, order_id: str, *, portfolio_id: str | None = None) -> list[Order]:
    query = db.query(Order).filter(Order.id == order_id)
    if portfolio_id:
        query = query.filter(Order.portfolio_id == portfolio_id)
    order = query.first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    root_id = order.parent_order_id or order.id
    linked_query = db.query(Order).filter(or_(Order.id == root_id, Order.parent_order_id == root_id))
    if portfolio_id:
        linked_query = linked_query.filter(Order.portfolio_id == portfolio_id)
    return linked_query.order_by(Order.parent_order_id.is_not(None).asc(), Order.created_at.asc()).all()


def place_bracket_order(
    db: Session,
    payload: BracketOrderRequest,
    *,
    actor_type: str,
    actor_id: str | None,
) -> tuple[Order, Order, Order]:
    if not payload.idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bracket orders require idempotency_key")

    existing_parent = db.query(Order).filter(Order.idempotency_key == payload.idempotency_key).first()
    if existing_parent:
        linked = list_linked_orders(db, existing_parent.id, portfolio_id=payload.portfolio_id)
        if len(linked) >= 3:
            by_link_type = {order.link_type: order for order in linked}
            return by_link_type["ENTRY"], by_link_type["STOP_LOSS"], by_link_type["TARGET"]

    entry_order = place_order(
        db,
        OrderRequest(
            portfolio_id=payload.portfolio_id,
            symbol=payload.symbol,
            expiry=payload.expiry,
            strike=payload.strike,
            option_type=payload.option_type,
            side=payload.side,
            order_type=payload.entry_order_type,
            product=payload.product,
            validity=payload.validity,
            lots=payload.lots,
            price=payload.entry_price,
            idempotency_key=payload.idempotency_key,
        ),
        actor_type=actor_type,
        actor_id=actor_id,
        source="bracket",
        auto_commit=False,
    )
    entry_order = _lock_query(db.query(Order).filter(Order.id == entry_order.id), db).first()
    if not entry_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry order not found")

    exit_side = "SELL" if entry_order.side == "BUY" else "BUY"
    entry_order.link_type = "ENTRY"
    entry_order.source = "bracket"

    stop_order = Order(
        portfolio_id=entry_order.portfolio_id,
        symbol=entry_order.symbol,
        security_id=entry_order.security_id,
        expiry=entry_order.expiry,
        strike=entry_order.strike,
        option_type=entry_order.option_type,
        side=exit_side,
        order_type="SL",
        product=entry_order.product,
        validity=entry_order.validity,
        lots=entry_order.lots,
        quantity=entry_order.quantity,
        price=payload.stop_loss_price,
        trigger_price=payload.stop_loss_trigger_price,
        status="PARKED",
        last_price=entry_order.last_price,
        parent_order_id=entry_order.id,
        link_type="STOP_LOSS",
        source="bracket",
        idempotency_key=f"{payload.idempotency_key}:stop",
        message="Waiting for entry fill",
    )
    target_order = Order(
        portfolio_id=entry_order.portfolio_id,
        symbol=entry_order.symbol,
        security_id=entry_order.security_id,
        expiry=entry_order.expiry,
        strike=entry_order.strike,
        option_type=entry_order.option_type,
        side=exit_side,
        order_type="LIMIT",
        product=entry_order.product,
        validity=entry_order.validity,
        lots=entry_order.lots,
        quantity=entry_order.quantity,
        price=payload.target_price,
        status="PARKED",
        last_price=entry_order.last_price,
        parent_order_id=entry_order.id,
        link_type="TARGET",
        source="bracket",
        idempotency_key=f"{payload.idempotency_key}:target",
        message="Waiting for entry fill",
    )
    db.add(stop_order)
    db.add(target_order)
    db.flush()

    log_audit(
        db,
        actor_type=actor_type,
        actor_id=actor_id,
        action="order.bracket_created",
        entity_type="order",
        entity_id=entry_order.id,
        details={"symbol": entry_order.symbol, "child_order_ids": [stop_order.id, target_order.id]},
    )

    if entry_order.status == "FILLED":
        _activate_bracket_children(db, entry_order, actor_type=actor_type, actor_id=actor_id)

    db.commit()
    db.refresh(entry_order)
    db.refresh(stop_order)
    db.refresh(target_order)
    return entry_order, stop_order, target_order


def list_positions(db: Session, portfolio_id: str | None = None) -> list[Position]:
    query = db.query(Position).filter(Position.net_quantity != 0)
    if portfolio_id:
        query = query.filter(Position.portfolio_id == portfolio_id)
    positions = query.order_by(Position.updated_at.desc()).all()
    for position in positions:
        _refresh_position_mark(position)
    db.flush()
    return positions


def close_position(
    db: Session,
    position_id: str,
    *,
    actor_type: str,
    actor_id: str | None,
    quantity: int | None = None,
) -> Order:
    position = _lock_query(
        db.query(Position).filter(Position.id == position_id, Position.net_quantity != 0),
        db,
    ).first()
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    close_quantity = abs(position.net_quantity)
    if quantity is not None:
        if quantity <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity must be positive")
        if quantity > close_quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity exceeds open position")
        if quantity % position.lot_size != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quantity must be a multiple of {position.lot_size}",
            )
        close_quantity = quantity
    payload = OrderRequest(
        portfolio_id=position.portfolio_id,
        expiry=position.expiry,
        strike=position.strike,
        option_type=position.option_type,
        side="SELL" if position.net_quantity > 0 else "BUY",
        order_type="MARKET",
        product=position.product,
        lots=max((close_quantity + position.lot_size - 1) // position.lot_size, 1),
    )
    return place_order(
        db,
        payload,
        actor_type=actor_type,
        actor_id=actor_id,
        source="close",
        quantity_override=close_quantity,
    )


def close_all_positions(db: Session, portfolio_id: str, *, actor_type: str, actor_id: str | None) -> list[Order]:
    positions = (
        db.query(Position)
        .filter(Position.portfolio_id == portfolio_id, Position.net_quantity != 0)
        .order_by(Position.updated_at.desc())
        .all()
    )
    return [close_position(db, position.id, actor_type=actor_type, actor_id=actor_id) for position in positions]


def funds_summary(db: Session, portfolio_id: str) -> FundsResponse:
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    positions = db.query(Position).filter(Position.portfolio_id == portfolio_id, Position.net_quantity != 0).all()
    unrealized = Decimal("0.00")
    for position in positions:
        _refresh_position_mark(position)
        unrealized += _money(_position_unrealized(position))
    db.flush()
    available = _available_funds(portfolio)
    total_equity = _to_float(_money(portfolio.cash_balance) + unrealized)
    return FundsResponse(
        portfolio_id=portfolio.id,
        cash_balance=_to_float(_money(portfolio.cash_balance)),
        blocked_margin=_to_float(_money(portfolio.blocked_margin)),
        blocked_premium=_to_float(_money(portfolio.blocked_premium)),
        available_funds=available,
        realized_pnl=_to_float(_money(portfolio.realized_pnl)),
        unrealized_pnl=_to_float(unrealized),
        total_equity=total_equity,
    )


def portfolio_summary(db: Session, portfolio: Portfolio) -> dict[str, Any]:
    funds = funds_summary(db, portfolio.id)
    return {
        "id": portfolio.id,
        "kind": portfolio.kind,
        "name": portfolio.name,
        "description": portfolio.description,
        "starting_cash": portfolio.starting_cash,
        "cash_balance": funds.cash_balance,
        "blocked_margin": funds.blocked_margin,
        "blocked_premium": funds.blocked_premium,
        "realized_pnl": funds.realized_pnl,
        "available_funds": funds.available_funds,
        "total_equity": funds.total_equity,
    }
