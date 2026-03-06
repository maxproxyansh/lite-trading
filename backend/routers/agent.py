from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import require_agent_scope
from rate_limit import rate_limit
from models import Signal
from schemas import FundsResponse, OrderRequest, OrderSummary, SignalIngestRequest, SignalResponse
from services.signal_adapter import signal_adapter
from services.trading_service import close_position, funds_summary, list_positions, place_order


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/agent", tags=["agent"])


@router.post("/orders", response_model=OrderSummary)
def agent_order(
    payload: OrderRequest,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("orders:write")),
    _: None = Depends(rate_limit("agent:orders", 120, 60)),
):
    order = place_order(db, payload, actor_type="agent", actor_id=key.id, source="agent")
    return OrderSummary.model_validate(order)


@router.get("/funds/{portfolio_id}", response_model=FundsResponse)
def agent_funds(portfolio_id: str, db: Session = Depends(get_db), key=Depends(require_agent_scope("funds:read"))):
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
    order = close_position(db, position_id, actor_type="agent", actor_id=key.id)
    return OrderSummary.model_validate(order)
