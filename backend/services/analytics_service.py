from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from models import Fill, Order, Portfolio, Position
from schemas import AnalyticsPoint, AnalyticsResponse
from services.trading_service import _position_unrealized, _refresh_position_mark, funds_summary


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
    pnl_by_day: dict[str, float] = defaultdict(float)
    equity_curve: list[AnalyticsPoint] = []
    running = portfolio.starting_cash
    for fill in fills:
        running = running + ((fill.price * fill.quantity) if fill.side == "SELL" else -(fill.price * fill.quantity)) - fill.charges
        day_label = fill.executed_at.date().isoformat()
        pnl_by_day[day_label] = round(running - portfolio.starting_cash, 2)
        equity_curve.append(AnalyticsPoint(label=fill.executed_at.isoformat(), value=round(running, 2)))

    for position in positions:
        _refresh_position_mark(position)
        if position.realized_pnl > 0:
            wins += 1
        elif position.realized_pnl < 0:
            losses += 1
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
        pnl_by_day=[AnalyticsPoint(label=label, value=value) for label, value in sorted(pnl_by_day.items())],
    )
