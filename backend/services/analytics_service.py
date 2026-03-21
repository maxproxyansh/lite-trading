from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from math import sqrt

from sqlalchemy.orm import Session

from config import get_settings
from models import Fill, Order, Portfolio, Position
from schemas import (
    AnalyticsAttribution,
    AnalyticsPoint,
    AnalyticsResponse,
    DetailedAnalyticsResponse,
    DetailedTradeSummary,
    EnrichedAnalyticsResponse,
)
from services.trading_service import _position_unrealized, _refresh_position_mark, funds_summary


def _money(value: float | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _expiry_from_symbol(symbol: str) -> str:
    """Extract expiry date string (YYYY-MM-DD) from NIFTY_YYYY-MM-DD_STRIKE_CE/PE."""
    try:
        return symbol.split("_")[1]
    except IndexError:
        return ""


def _safe_date(date_str: str) -> date | None:
    """Parse YYYY-MM-DD string to date, return None on failure."""
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _days_between(d1: date | None, d2: date | None) -> int:
    if d1 is None or d2 is None:
        return 0
    return (d1 - d2).days


def _build_closed_trades(fills: list[Fill]) -> list[DetailedTradeSummary]:
    settings = get_settings()
    lot_size = settings.nifty_lot_size

    open_lots: dict[tuple[str, str], list[dict]] = defaultdict(list)
    closed_trades: list[DetailedTradeSummary] = []

    for fill in fills:
        fill_price = _money(fill.price)
        fill_charges = _money(fill.charges)
        remaining = fill.quantity
        bucket = open_lots[(fill.symbol, fill.side)]
        opposite_key = (fill.symbol, "SELL" if fill.side == "BUY" else "BUY")
        opposite_bucket = open_lots[opposite_key]
        charge_per_unit = (fill_charges / Decimal(fill.quantity)) if fill.quantity else Decimal("0.00")

        fill_spot = float(fill.spot_at_fill) if fill.spot_at_fill is not None else None
        fill_vix = float(fill.vix_at_fill) if fill.vix_at_fill is not None else None

        if fill.side == "BUY":
            while remaining > 0 and opposite_bucket:
                open_lot = opposite_bucket[0]
                open_qty = int(open_lot["qty"])
                close_qty = min(open_qty, remaining)
                entry_charge = open_lot["charge_per_unit"] * Decimal(close_qty)
                exit_charge = charge_per_unit * Decimal(close_qty)
                pnl = (_money(open_lot["price"]) - fill_price) * Decimal(close_qty) - entry_charge - exit_charge

                strike = int(open_lot["strike"])
                expiry_str = str(open_lot["expiry_date"])
                expiry_d = _safe_date(expiry_str)
                entry_date = open_lot["executed_at"].date() if hasattr(open_lot["executed_at"], "date") else None
                exit_date = fill.executed_at.date()
                spot_entry = open_lot.get("spot")
                spot_exit = fill_spot
                vix_entry = open_lot.get("vix")
                vix_exit = fill_vix

                closed_trades.append(
                    DetailedTradeSummary(
                        symbol=fill.symbol,
                        strike=strike,
                        option_type=str(open_lot["option_type"]),
                        direction="SHORT",
                        quantity=close_qty,
                        lots=close_qty // lot_size,
                        entry_time=open_lot["executed_at"],
                        exit_time=fill.executed_at,
                        hold_seconds=max((fill.executed_at - open_lot["executed_at"]).total_seconds(), 0.0),
                        hold_days=(exit_date - entry_date).days if entry_date and exit_date else 0,
                        realized_pnl=float(pnl),
                        entry_price=float(open_lot["price"]),
                        exit_price=float(fill_price),
                        expiry_date=expiry_str,
                        days_to_expiry_at_entry=_days_between(expiry_d, entry_date),
                        days_to_expiry_at_exit=_days_between(expiry_d, exit_date),
                        spot_at_entry=spot_entry,
                        spot_at_exit=spot_exit,
                        vix_at_entry=vix_entry,
                        vix_at_exit=vix_exit,
                        atm_distance=(strike - int(spot_entry)) if spot_entry is not None else None,
                    )
                )
                open_qty -= close_qty
                remaining -= close_qty
                if open_qty == 0:
                    opposite_bucket.pop(0)
                else:
                    open_lot["qty"] = open_qty
            if remaining > 0:
                bucket.append(
                    {
                        "qty": remaining,
                        "price": fill_price,
                        "charge_per_unit": charge_per_unit,
                        "strike": _strike_from_symbol(fill.symbol),
                        "option_type": _option_type_from_symbol(fill.symbol),
                        "expiry_date": _expiry_from_symbol(fill.symbol),
                        "executed_at": fill.executed_at,
                        "spot": fill_spot,
                        "vix": fill_vix,
                    }
                )
        else:
            while remaining > 0 and opposite_bucket:
                open_lot = opposite_bucket[0]
                open_qty = int(open_lot["qty"])
                close_qty = min(open_qty, remaining)
                entry_charge = open_lot["charge_per_unit"] * Decimal(close_qty)
                exit_charge = charge_per_unit * Decimal(close_qty)
                pnl = (fill_price - _money(open_lot["price"])) * Decimal(close_qty) - entry_charge - exit_charge

                strike = int(open_lot["strike"])
                expiry_str = str(open_lot["expiry_date"])
                expiry_d = _safe_date(expiry_str)
                entry_date = open_lot["executed_at"].date() if hasattr(open_lot["executed_at"], "date") else None
                exit_date = fill.executed_at.date()
                spot_entry = open_lot.get("spot")
                spot_exit = fill_spot
                vix_entry = open_lot.get("vix")
                vix_exit = fill_vix

                closed_trades.append(
                    DetailedTradeSummary(
                        symbol=fill.symbol,
                        strike=strike,
                        option_type=str(open_lot["option_type"]),
                        direction="LONG",
                        quantity=close_qty,
                        lots=close_qty // lot_size,
                        entry_time=open_lot["executed_at"],
                        exit_time=fill.executed_at,
                        hold_seconds=max((fill.executed_at - open_lot["executed_at"]).total_seconds(), 0.0),
                        hold_days=(exit_date - entry_date).days if entry_date and exit_date else 0,
                        realized_pnl=float(pnl),
                        entry_price=float(open_lot["price"]),
                        exit_price=float(fill_price),
                        expiry_date=expiry_str,
                        days_to_expiry_at_entry=_days_between(expiry_d, entry_date),
                        days_to_expiry_at_exit=_days_between(expiry_d, exit_date),
                        spot_at_entry=spot_entry,
                        spot_at_exit=spot_exit,
                        vix_at_entry=vix_entry,
                        vix_at_exit=vix_exit,
                        atm_distance=(strike - int(spot_entry)) if spot_entry is not None else None,
                    )
                )
                open_qty -= close_qty
                remaining -= close_qty
                if open_qty == 0:
                    opposite_bucket.pop(0)
                else:
                    open_lot["qty"] = open_qty
            if remaining > 0:
                bucket.append(
                    {
                        "qty": remaining,
                        "price": fill_price,
                        "charge_per_unit": charge_per_unit,
                        "strike": _strike_from_symbol(fill.symbol),
                        "option_type": _option_type_from_symbol(fill.symbol),
                        "expiry_date": _expiry_from_symbol(fill.symbol),
                        "executed_at": fill.executed_at,
                        "spot": fill_spot,
                        "vix": fill_vix,
                    }
                )

    return closed_trades


def _strike_from_symbol(symbol: str) -> int:
    try:
        return int(symbol.split("_")[2])
    except (IndexError, ValueError):
        return 0


def _option_type_from_symbol(symbol: str) -> str:
    try:
        return symbol.split("_")[3]
    except IndexError:
        return ""


def _histogram(trades: list[DetailedTradeSummary]) -> list[AnalyticsPoint]:
    buckets = {
        "<=-500": 0,
        "-500:-100": 0,
        "-100:0": 0,
        "0:100": 0,
        "100:500": 0,
        ">=500": 0,
    }
    for trade in trades:
        pnl = trade.realized_pnl
        if pnl <= -500:
            buckets["<=-500"] += 1
        elif pnl < -100:
            buckets["-500:-100"] += 1
        elif pnl < 0:
            buckets["-100:0"] += 1
        elif pnl < 100:
            buckets["0:100"] += 1
        elif pnl < 500:
            buckets["100:500"] += 1
        else:
            buckets[">=500"] += 1
    return [AnalyticsPoint(label=label, value=float(value)) for label, value in buckets.items()]


def _risk_ratios(trades: list[DetailedTradeSummary], starting_cash: float) -> tuple[float, float, float, list[AnalyticsPoint], list[AnalyticsPoint]]:
    if not trades:
        return 0.0, 0.0, 0.0, [], []

    equity = Decimal(str(starting_cash))
    peak = equity
    returns: list[float] = []
    downside_returns: list[float] = []
    equity_curve: list[AnalyticsPoint] = []
    drawdown_curve: list[AnalyticsPoint] = []
    for trade in sorted(trades, key=lambda item: item.exit_time):
        starting_equity = max(float(equity), 1.0)
        equity += Decimal(str(trade.realized_pnl))
        trade_return = trade.realized_pnl / starting_equity
        returns.append(trade_return)
        if trade_return < 0:
            downside_returns.append(trade_return)
        if equity > peak:
            peak = equity
        drawdown = max(float(peak - equity), 0.0)
        equity_curve.append(AnalyticsPoint(label=trade.exit_time.isoformat(), value=float(equity)))
        drawdown_curve.append(AnalyticsPoint(label=trade.exit_time.isoformat(), value=drawdown))

    n = len(returns)
    mean_return = sum(returns) / n
    variance = sum((value - mean_return) ** 2 for value in returns) / (n - 1) if n > 1 else 0.0
    downside_mean = sum(downside_returns) / len(downside_returns) if downside_returns else 0.0
    downside_variance = (
        sum((value - downside_mean) ** 2 for value in downside_returns) / (len(downside_returns) - 1)
        if len(downside_returns) > 1
        else 0.0
    )
    annualize = sqrt(252)
    sharpe = (mean_return / sqrt(variance)) * annualize if variance > 0 else 0.0
    sortino = (mean_return / sqrt(downside_variance)) * annualize if downside_variance > 0 else 0.0
    max_drawdown = max((point.value for point in drawdown_curve), default=0.0)
    total_return = (float(equity) - starting_cash) / max(starting_cash, 1.0)
    calmar = total_return / (max_drawdown / max(starting_cash, 1.0)) if max_drawdown > 0 else 0.0
    return round(sharpe, 4), round(sortino, 4), round(calmar, 4), equity_curve, drawdown_curve


def _consecutive_streaks(trades: list[DetailedTradeSummary]) -> tuple[int, int]:
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0
    for trade in sorted(trades, key=lambda item: item.exit_time):
        if trade.realized_pnl > 0:
            current_wins += 1
            current_losses = 0
        elif trade.realized_pnl < 0:
            current_losses += 1
            current_wins = 0
        else:
            current_wins = 0
            current_losses = 0
        max_wins = max(max_wins, current_wins)
        max_losses = max(max_losses, current_losses)
    return max_wins, max_losses


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


def detailed_analytics_summary(
    db: Session,
    portfolio_id: str,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
) -> DetailedAnalyticsResponse:
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise ValueError("Portfolio not found")

    fill_query = db.query(Fill).filter(Fill.portfolio_id == portfolio_id)
    if to_date is not None:
        fill_query = fill_query.filter(Fill.executed_at < datetime.combine(to_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1))
    fills = fill_query.order_by(Fill.executed_at.asc()).all()
    funds = funds_summary(db, portfolio_id)

    closed_trades = [
        trade
        for trade in _build_closed_trades(fills)
        if (from_date is None or trade.exit_time.date() >= from_date)
        and (to_date is None or trade.exit_time.date() <= to_date)
    ]
    attribution_map: dict[tuple[str, int, str, str], dict[str, float | int | str]] = defaultdict(
        lambda: {"closed_trades": 0, "realized_pnl": 0.0}
    )
    for trade in closed_trades:
        key = (trade.symbol, trade.strike, trade.option_type, trade.direction)
        attribution_map[key]["closed_trades"] = int(attribution_map[key]["closed_trades"]) + 1
        attribution_map[key]["realized_pnl"] = float(attribution_map[key]["realized_pnl"]) + trade.realized_pnl

    attribution = [
        AnalyticsAttribution(
            symbol=symbol,
            strike=strike,
            option_type=option_type,
            direction=direction,
            closed_trades=int(values["closed_trades"]),
            realized_pnl=round(float(values["realized_pnl"]), 2),
        )
        for (symbol, strike, option_type, direction), values in sorted(attribution_map.items())
    ]

    sharpe, sortino, calmar, _, drawdown_curve = _risk_ratios(closed_trades, float(portfolio.starting_cash))

    average_hold_seconds = (
        sum(trade.hold_seconds for trade in closed_trades) / len(closed_trades)
        if closed_trades
        else 0.0
    )
    max_consecutive_wins, max_consecutive_losses = _consecutive_streaks(closed_trades)

    return DetailedAnalyticsResponse(
        portfolio_id=portfolio_id,
        from_date=from_date,
        to_date=to_date,
        total_closed_trades=len(closed_trades),
        realized_pnl=round(sum(trade.realized_pnl for trade in closed_trades), 2),
        unrealized_pnl=round(funds.unrealized_pnl, 2),
        total_equity=round(funds.total_equity, 2),
        trade_attribution=attribution,
        closed_trades=closed_trades,
        drawdown_curve=drawdown_curve,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        win_loss_distribution=_histogram(closed_trades),
        average_hold_seconds=round(average_hold_seconds, 2),
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
    )


def enriched_analytics_summary(db: Session, portfolio_id: str) -> EnrichedAnalyticsResponse:
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise ValueError("Portfolio not found")

    fills = db.query(Fill).filter(Fill.portfolio_id == portfolio_id).order_by(Fill.executed_at.asc()).all()
    funds = funds_summary(db, portfolio_id)

    closed_trades = _build_closed_trades(fills)

    # Reuse _risk_ratios for sharpe, sortino, equity_curve, drawdown_curve
    sharpe, sortino, _calmar, equity_curve, drawdown_curve = _risk_ratios(closed_trades, float(portfolio.starting_cash))
    max_drawdown = max((p.value for p in drawdown_curve), default=0.0)

    # Reuse analytics_summary logic for pnl_by_day
    basic = analytics_summary(db, portfolio_id)
    pnl_by_day = basic.pnl_by_day

    # Win/loss classification
    wins = [t for t in closed_trades if t.realized_pnl > 0]
    losses = [t for t in closed_trades if t.realized_pnl < 0]
    total = len(closed_trades)

    win_rate = round((len(wins) / total) * 100, 2) if total else 0.0

    total_win_pnl = sum(t.realized_pnl for t in wins)
    total_loss_pnl = sum(t.realized_pnl for t in losses)
    avg_win = total_win_pnl / len(wins) if wins else 0.0
    avg_loss = abs(total_loss_pnl / len(losses)) if losses else 0.0

    # Expectancy: avg_win * win_prob - avg_loss * loss_prob
    decided = len(wins) + len(losses)
    win_prob = len(wins) / decided if decided else 0.0
    loss_prob = len(losses) / decided if decided else 0.0
    expectancy = round(avg_win * win_prob - avg_loss * loss_prob, 2)

    # Risk/reward: avg_win / avg_loss
    risk_reward = round(avg_win / avg_loss, 4) if avg_loss > 0 else 0.0

    # Profit factor: gross_wins / gross_losses
    profit_factor = round(total_win_pnl / abs(total_loss_pnl), 4) if total_loss_pnl != 0 else 0.0

    biggest_win = max((t.realized_pnl for t in closed_trades), default=0.0)
    biggest_loss = min((t.realized_pnl for t in closed_trades), default=0.0)

    max_consecutive_wins, max_consecutive_losses = _consecutive_streaks(closed_trades)

    # Hold time stats
    avg_hold_seconds = round(sum(t.hold_seconds for t in closed_trades) / total, 2) if total else 0.0
    avg_win_hold_seconds = round(sum(t.hold_seconds for t in wins) / len(wins), 2) if wins else 0.0
    avg_loss_hold_seconds = round(sum(t.hold_seconds for t in losses) / len(losses), 2) if losses else 0.0

    return EnrichedAnalyticsResponse(
        portfolio_id=portfolio_id,
        total_closed_trades=total,
        realized_pnl=round(sum(t.realized_pnl for t in closed_trades), 2),
        unrealized_pnl=round(funds.unrealized_pnl, 2),
        total_equity=round(funds.total_equity, 2),
        win_rate=win_rate,
        expectancy=expectancy,
        risk_reward=risk_reward,
        profit_factor=profit_factor,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown=round(max_drawdown, 2),
        biggest_win=round(biggest_win, 2),
        biggest_loss=round(biggest_loss, 2),
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
        avg_hold_seconds=avg_hold_seconds,
        avg_win_hold_seconds=avg_win_hold_seconds,
        avg_loss_hold_seconds=avg_loss_hold_seconds,
        equity_curve=equity_curve,
        pnl_by_day=pnl_by_day,
        drawdown_curve=drawdown_curve,
        closed_trades=closed_trades,
    )
