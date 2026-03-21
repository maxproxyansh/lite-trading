from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user, get_user_portfolio_ids
from models import Position
from schemas import PositionSummary
from services.trading_service import _position_unrealized, close_position, list_positions


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/positions", tags=["positions"])


def _serialize_position(position) -> PositionSummary:
    return PositionSummary(
        id=position.id,
        portfolio_id=position.portfolio_id,
        symbol=position.symbol,
        expiry=position.expiry,
        strike=position.strike,
        option_type=position.option_type,
        product=position.product,
        net_quantity=position.net_quantity,
        lot_size=position.lot_size,
        average_open_price=position.average_open_price,
        last_price=position.last_price,
        blocked_margin=position.blocked_margin,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=_position_unrealized(position),
        opened_at=position.opened_at,
    )


@router.get("", response_model=list[PositionSummary])
def positions(
    portfolio_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    user_portfolio_ids: list[str] = Depends(get_user_portfolio_ids),
):
    if portfolio_id and portfolio_id not in user_portfolio_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    target_id = portfolio_id if portfolio_id else (user_portfolio_ids[0] if user_portfolio_ids else None)
    if not target_id:
        return []
    return [_serialize_position(p) for p in list_positions(db, target_id)]


@router.post("/{position_id}/close", response_model=PositionSummary)
def close(
    position_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    user_portfolio_ids: list[str] = Depends(get_user_portfolio_ids),
):
    pos = db.query(Position).filter(Position.id == position_id).first()
    if not pos or pos.portfolio_id not in user_portfolio_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    order = close_position(db, position_id, actor_type="user", actor_id=user.id)
    positions_now = list_positions(db, order.portfolio_id)
    target = next((p for p in positions_now if p.symbol == order.symbol), None)
    if not target:
        return PositionSummary(
            id=position_id,
            portfolio_id=order.portfolio_id,
            symbol=order.symbol,
            expiry=order.expiry,
            strike=order.strike,
            option_type=order.option_type,
            product=order.product,
            net_quantity=0,
            lot_size=pos.lot_size,
            average_open_price=0.0,
            last_price=order.average_price or 0.0,
            blocked_margin=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            opened_at=order.requested_at,
        )
    return _serialize_position(target)
