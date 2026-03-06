from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from models import Fill, Order, Portfolio, Position
from schemas import FundsResponse, OrderRequest
from services.audit import log_audit
from services.market_data import market_data_service


settings = get_settings()
LOT_SIZE = 25


@dataclass
class QuoteContext:
    symbol: str
    security_id: str | None
    ltp: float
    bid: float | None
    ask: float | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _available_funds(portfolio: Portfolio) -> float:
    return round(portfolio.cash_balance - portfolio.blocked_margin - portfolio.blocked_premium, 2)


def _estimate_charges(price: float, quantity: int, side: str) -> float:
    turnover = price * quantity
    brokerage = min(turnover * 0.0003, 20.0)
    stt = turnover * (0.0005 if side == "SELL" else 0.0)
    exchange_txn = turnover * 0.00053
    sebi = turnover * 0.000001
    gst = (brokerage + exchange_txn) * 0.18
    stamp = turnover * (0.00003 if side == "BUY" else 0.0)
    return round(brokerage + stt + exchange_txn + sebi + gst + stamp, 2)


def _fallback_short_margin(price: float, quantity: int) -> float:
    return round(max(price * quantity * 2.5, 25000.0), 2)


def _margin_from_dhan(security_id: str | None, side: str, quantity: int, price: float, product: str) -> float | None:
    if side != "SELL" or not security_id or not settings.dhan_client_id or not settings.dhan_access_token:
        return None
    try:
        from dhanhq import dhanhq as Dhanhq

        client = Dhanhq(settings.dhan_client_id, settings.dhan_access_token)
        response = client.margin_calculator(
            security_id=security_id,
            exchange_segment="NSE_FNO",
            transaction_type=side,
            quantity=quantity,
            product_type="INTRA" if product == "MIS" else "MARGIN",
            price=price,
        )
    except Exception:  # noqa: BLE001
        return None

    payload = response.get("data", {}) if isinstance(response, dict) else {}
    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    for key in ("total_margin", "totalMarginRequired", "margin_required", "required_margin", "margin"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if value is not None:
            try:
                return round(float(value), 2)
            except (TypeError, ValueError):
                continue
    return None


def _quote_context(order: OrderRequest) -> QuoteContext:
    symbol = order.symbol or market_data_service.resolve_symbol(
        expiry=order.expiry,
        strike=order.strike,
        option_type=order.option_type,
    )
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
    position = db.query(Position).filter(
        Position.portfolio_id == portfolio_id,
        Position.symbol == symbol,
        Position.product == product,
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

    if existing_qty == 0:
        position.net_quantity = quantity if side == "BUY" else -quantity
        position.average_open_price = price
        position.blocked_margin = margin_required if side == "SELL" else 0.0
        return realized_delta, released_margin

    if existing_qty > 0 and side == "BUY":
        total_cost = (position.average_open_price * existing_qty) + (price * quantity)
        position.net_quantity = existing_qty + quantity
        position.average_open_price = total_cost / position.net_quantity
        return realized_delta, released_margin

    if existing_qty < 0 and side == "SELL":
        current_abs = abs(existing_qty)
        total_credit = (position.average_open_price * current_abs) + (price * quantity)
        position.net_quantity = -(current_abs + quantity)
        position.average_open_price = total_credit / abs(position.net_quantity)
        position.blocked_margin += margin_required
        return realized_delta, released_margin

    if existing_qty > 0 and side == "SELL":
        close_qty = min(existing_qty, quantity)
        realized_delta = (price - position.average_open_price) * close_qty
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
            position.average_open_price = price
            position.blocked_margin = margin_required
        return realized_delta, released_margin

    if existing_qty < 0 and side == "BUY":
        short_abs = abs(existing_qty)
        close_qty = min(short_abs, quantity)
        realized_delta = (position.average_open_price - price) * close_qty
        release_ratio = close_qty / short_abs if short_abs else 0.0
        released_margin = round(position.blocked_margin * release_ratio, 2)
        position.blocked_margin = max(position.blocked_margin - released_margin, 0.0)
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
            position.average_open_price = price
            position.blocked_margin = 0.0
        return realized_delta, released_margin

    return realized_delta, released_margin


def _refresh_position_mark(position: Position) -> None:
    quote = market_data_service.get_quote(position.symbol)
    if quote and quote.get("ltp") is not None:
        position.last_price = float(quote["ltp"])


def _position_unrealized(position: Position) -> float:
    if position.net_quantity == 0:
        return 0.0
    if position.net_quantity > 0:
        return round((position.last_price - position.average_open_price) * position.net_quantity, 2)
    return round((position.average_open_price - position.last_price) * abs(position.net_quantity), 2)


def place_order(
    db: Session,
    payload: OrderRequest,
    *,
    actor_type: str,
    actor_id: str | None,
    source: str,
) -> Order:
    if payload.idempotency_key:
        existing = db.query(Order).filter(Order.idempotency_key == payload.idempotency_key).first()
        if existing:
            return existing

    portfolio = db.query(Portfolio).filter(Portfolio.id == payload.portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    quote = _quote_context(payload)
    if quote.ltp <= 0:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MARKET_DATA_UNAVAILABLE")

    quantity = payload.lots * LOT_SIZE
    existing_position = db.query(Position).filter(
        Position.portfolio_id == payload.portfolio_id,
        Position.symbol == quote.symbol,
        Position.product == payload.product,
    ).first()
    existing_qty = existing_position.net_quantity if existing_position else 0
    reference_price = payload.price if payload.order_type in {"LIMIT", "SL"} and payload.price else _price_for_market(quote, payload.side)
    charges = _estimate_charges(reference_price, quantity, payload.side)
    premium_required = round(reference_price * quantity, 2) if payload.side == "BUY" else 0.0
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

    if _available_funds(portfolio) < premium_required + margin_required + charges:
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
        lots=payload.lots,
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
            portfolio.blocked_premium += premium_required
        else:
            portfolio.blocked_margin += margin_required or 0.0
        log_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="order.placed",
            entity_type="order",
            entity_id=order.id,
            details={"status": order.status, "symbol": order.symbol},
        )
        db.commit()
        db.refresh(order)
        return order

    _fill_order(
        db,
        order,
        fill_price=_price_for_market(quote, payload.side) if payload.order_type in {"MARKET", "SL-M"} else reference_price,
        actor_type=actor_type,
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(order)
    return order


def _fill_order(db: Session, order: Order, *, fill_price: float, actor_type: str, actor_id: str | None) -> None:
    portfolio = db.query(Portfolio).filter(Portfolio.id == order.portfolio_id).first()
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

    if was_pending and order.side == "BUY":
        portfolio.blocked_premium = max(portfolio.blocked_premium - order.premium_required, 0.0)

    realized_delta, released_margin = _apply_fill_to_position(position, order.side, order.quantity, fill_price, order.margin_required)
    position.realized_pnl += realized_delta
    position.last_price = fill_price
    portfolio.realized_pnl += realized_delta

    if order.side == "BUY":
        portfolio.cash_balance -= (fill_price * order.quantity) + order.charges
        if released_margin:
            portfolio.blocked_margin = max(portfolio.blocked_margin - released_margin, 0.0)
    else:
        portfolio.cash_balance += (fill_price * order.quantity) - order.charges
        if not was_pending and order.margin_required:
            portfolio.blocked_margin += order.margin_required

    order.status = "FILLED"
    order.average_price = fill_price
    order.filled_quantity = order.quantity
    order.filled_at = _utcnow()
    order.updated_at = _utcnow()

    fill = Fill(
        order_id=order.id,
        portfolio_id=order.portfolio_id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=fill_price,
        charges=order.charges,
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


async def process_open_orders() -> None:
    return None


def process_open_orders_sync(db: Session) -> int:
    changed = 0
    open_orders = db.query(Order).filter(Order.status.in_(("OPEN", "TRIGGER_PENDING"))).all()
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
        order.last_price = quote.ltp
        if should_fill:
            _fill_order(
                db,
                order,
                fill_price=_price_for_market(quote, order.side) if order.order_type in {"MARKET", "SL-M"} else float(order.price or quote.ltp),
                actor_type="system",
                actor_id=None,
            )
            changed += 1
        else:
            order.status = next_status
    if changed:
        db.commit()
    return changed


def list_orders(db: Session, portfolio_id: str | None = None) -> list[Order]:
    query = db.query(Order).order_by(Order.requested_at.desc())
    if portfolio_id:
        query = query.filter(Order.portfolio_id == portfolio_id)
    return query.all()


def list_positions(db: Session, portfolio_id: str | None = None) -> list[Position]:
    query = db.query(Position).filter(Position.net_quantity != 0)
    if portfolio_id:
        query = query.filter(Position.portfolio_id == portfolio_id)
    positions = query.order_by(Position.updated_at.desc()).all()
    for position in positions:
        _refresh_position_mark(position)
    db.flush()
    return positions


def close_position(db: Session, position_id: str, *, actor_type: str, actor_id: str | None) -> Order:
    position = db.query(Position).filter(Position.id == position_id, Position.net_quantity != 0).first()
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    payload = OrderRequest(
        portfolio_id=position.portfolio_id,
        expiry=position.expiry,
        strike=position.strike,
        option_type=position.option_type,
        side="SELL" if position.net_quantity > 0 else "BUY",
        order_type="MARKET",
        product=position.product,
        lots=max(abs(position.net_quantity) // LOT_SIZE, 1),
    )
    return place_order(db, payload, actor_type=actor_type, actor_id=actor_id, source="close")


def funds_summary(db: Session, portfolio_id: str) -> FundsResponse:
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    positions = db.query(Position).filter(Position.portfolio_id == portfolio_id, Position.net_quantity != 0).all()
    unrealized = 0.0
    for position in positions:
        _refresh_position_mark(position)
        unrealized += _position_unrealized(position)
    db.flush()
    available = _available_funds(portfolio)
    total_equity = round(portfolio.cash_balance + unrealized, 2)
    return FundsResponse(
        portfolio_id=portfolio.id,
        cash_balance=round(portfolio.cash_balance, 2),
        blocked_margin=round(portfolio.blocked_margin, 2),
        blocked_premium=round(portfolio.blocked_premium, 2),
        available_funds=available,
        realized_pnl=round(portfolio.realized_pnl, 2),
        unrealized_pnl=round(unrealized, 2),
        total_equity=total_equity,
    )


def portfolio_summary(db: Session, portfolio: Portfolio) -> dict[str, Any]:
    funds = funds_summary(db, portfolio.id)
    return {
        "id": portfolio.id,
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
