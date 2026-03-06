from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user
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
def positions(portfolio_id: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [_serialize_position(position) for position in list_positions(db, portfolio_id)]


@router.post("/{position_id}/close", response_model=PositionSummary)
def close(position_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    order = close_position(db, position_id, actor_type="user", actor_id=user.id)
    positions_now = list_positions(db, order.portfolio_id)
    target = next((position for position in positions_now if position.symbol == order.symbol), None)
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
            lot_size=25,
            average_open_price=0.0,
            last_price=order.average_price or 0.0,
            blocked_margin=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            opened_at=order.requested_at,
        )
    return _serialize_position(target)
