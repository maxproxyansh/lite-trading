from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from datetime import date

from sqlalchemy.orm import Session

from models import Fill, Order, Portfolio, Position
from schemas import AnalyticsPoint, AnalyticsResponse
from services.trading_service import _position_unrealized, _refresh_position_mark, funds_summary


def _money(value: float | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def analytics_summary(db: Session, portfolio_id: str) -> AnalyticsResponse:
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise ValueError("Portfolio not found")

    funds = funds_summary(db, portfolio_id)
    orders = db.query(Order).filter(Order.portfolio_id == portfolio_id).order_by(Order.requested_at.asc()).all()
    fills = db.query(Fill).filter(Fill.portfolio_id == portfolio_id).order_by(Fill.executed_at.asc()).all()
    positions = db.query(Position).filter(Position.portfolio_id == portfolio_id, Position.net_quantity != 0).all()

    wins = 0
    losses = 0
    pnl_by_day: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    equity_curve: list[AnalyticsPoint] = []
    running_cash = _money(portfolio.starting_cash)
    open_lots: dict[str, list[dict[str, Decimal | int | str]]] = defaultdict(list)
    for fill in fills:
        fill_price = _money(fill.price)
        fill_charges = _money(fill.charges)
        signed_cash = (fill_price * fill.quantity) if fill.side == "SELL" else -(fill_price * fill.quantity)
        running_cash = running_cash + signed_cash - fill_charges
        day_label = fill.executed_at.date().isoformat()
        remaining = fill.quantity
        bucket = open_lots[fill.symbol]
        charge_per_unit = (fill_charges / Decimal(fill.quantity)) if fill.quantity else Decimal("0.00")
        if fill.side == "BUY":
            while remaining > 0 and bucket and bucket[0]["side"] == "SELL":
                open_lot = bucket[0]
                open_qty = int(open_lot["qty"])
                close_qty = min(open_qty, remaining)
                open_price = open_lot["price"]
                entry_charge = open_lot["charge_per_unit"] * Decimal(close_qty)
                exit_charge = charge_per_unit * Decimal(close_qty)
                pnl = (open_price - fill_price) * Decimal(close_qty) - entry_charge - exit_charge
                pnl_by_day[day_label] += pnl
                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1
                open_qty -= close_qty
                remaining -= close_qty
                if open_qty == 0:
                    bucket.pop(0)
                else:
                    open_lot["qty"] = open_qty
            if remaining > 0:
                bucket.append({"side": "BUY", "qty": remaining, "price": fill_price, "charge_per_unit": charge_per_unit})
        else:
            while remaining > 0 and bucket and bucket[0]["side"] == "BUY":
                open_lot = bucket[0]
                open_qty = int(open_lot["qty"])
                close_qty = min(open_qty, remaining)
                open_price = open_lot["price"]
                entry_charge = open_lot["charge_per_unit"] * Decimal(close_qty)
                exit_charge = charge_per_unit * Decimal(close_qty)
                pnl = (fill_price - open_price) * Decimal(close_qty) - entry_charge - exit_charge
                pnl_by_day[day_label] += pnl
                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1
                open_qty -= close_qty
                remaining -= close_qty
                if open_qty == 0:
                    bucket.pop(0)
                else:
                    open_lot["qty"] = open_qty
            if remaining > 0:
                bucket.append({"side": "SELL", "qty": remaining, "price": fill_price, "charge_per_unit": charge_per_unit})
        equity_curve.append(AnalyticsPoint(label=fill.executed_at.isoformat(), value=float(running_cash)))

    current_unrealized = Decimal("0.00")
    for position in positions:
        _refresh_position_mark(position)
        current_unrealized += _money(_position_unrealized(position))
    equity_curve.append(AnalyticsPoint(label=date.today().isoformat(), value=float(_money(funds.total_equity))))

    pnl_by_day[date.today().isoformat()] += current_unrealized
    total_closed = wins + losses
    win_rate = round((wins / total_closed) * 100, 2) if total_closed else 0.0

    return AnalyticsResponse(
        portfolio_id=portfolio_id,
        total_orders=len(orders),
        filled_orders=sum(1 for order in orders if order.status == "FILLED"),
        win_rate=win_rate,
        realized_pnl=round(funds.realized_pnl, 2),
        unrealized_pnl=round(funds.unrealized_pnl, 2),
        total_equity=round(funds.total_equity, 2),
        equity_curve=equity_curve[-200:],
        pnl_by_day=[AnalyticsPoint(label=label, value=float(value)) for label, value in sorted(pnl_by_day.items())],
    )
