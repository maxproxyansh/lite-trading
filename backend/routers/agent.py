from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import require_agent_scope
from models import Position, Signal
from rate_limit import rate_limit
from schemas import FundsResponse, OrderRequest, OrderSummary, PositionSummary, SignalIngestRequest, SignalResponse
from services.signal_adapter import signal_adapter
from services.trading_service import _position_unrealized, close_position, funds_summary, list_orders, list_positions, place_order


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/agent", tags=["agent"])


def _ensure_agent_portfolio(key, portfolio_id: str) -> str:
    if key.portfolio_id != portfolio_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Portfolio not allowed for this API key")
    return portfolio_id


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


@router.post("/orders", response_model=OrderSummary)
def agent_order(
    payload: OrderRequest,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("orders:write")),
    _: None = Depends(rate_limit("agent:orders", 120, 60)),
):
    if not payload.idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent orders require idempotency_key")
    _ensure_agent_portfolio(key, payload.portfolio_id)
    order = place_order(db, payload, actor_type="agent", actor_id=key.id, source="agent")
    return OrderSummary.model_validate(order)


@router.get("/orders", response_model=list[OrderSummary])
def agent_orders(db: Session = Depends(get_db), key=Depends(require_agent_scope("orders:read"))):
    return [OrderSummary.model_validate(order) for order in list_orders(db, key.portfolio_id)]


@router.get("/positions", response_model=list[PositionSummary])
def agent_positions(db: Session = Depends(get_db), key=Depends(require_agent_scope("positions:read"))):
    return [_serialize_position(position) for position in list_positions(db, key.portfolio_id)]


@router.get("/funds/{portfolio_id}", response_model=FundsResponse)
def agent_funds(portfolio_id: str, db: Session = Depends(get_db), key=Depends(require_agent_scope("funds:read"))):
    _ensure_agent_portfolio(key, portfolio_id)
    return funds_summary(db, portfolio_id)


@router.get("/signals/latest", response_model=SignalResponse | None)
def agent_latest_signal(db: Session = Depends(get_db), key=Depends(require_agent_scope("signals:read"))):
    signal = db.query(Signal).order_by(Signal.generated_at.desc()).first()
    return SignalResponse.model_validate(signal) if signal else None


@router.post("/signals", response_model=SignalResponse | None)
async def agent_signal_ingest(
    payload: SignalIngestRequest,
    key=Depends(require_agent_scope("signals:write")),
    _: None = Depends(rate_limit("agent:signals", 120, 60)),
):
    signal = await signal_adapter.ingest_payload(payload.payload)
    return SignalResponse.model_validate(signal) if signal else None


@router.post("/positions/{position_id}/close", response_model=OrderSummary)
def agent_close(
    position_id: str,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("positions:write")),
    _: None = Depends(rate_limit("agent:close", 120, 60)),
):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position or position.portfolio_id != key.portfolio_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    order = close_position(db, position_id, actor_type="agent", actor_id=key.id)
    return OrderSummary.model_validate(order)
