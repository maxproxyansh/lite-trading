from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_agent_key, require_agent_scope
from models import Portfolio, Position, Signal, User
from rate_limit import rate_limit
from schemas import (
    AgentBootstrapRequest,
    AgentBootstrapResponse,
    AgentProfileResponse,
    DhanFundResponse,
    DhanOrderRequest,
    DhanOrderResponse,
    DhanPositionResponse,
    FundsResponse,
    OrderRequest,
    OrderSummary,
    PositionSummary,
    SignalIngestRequest,
    SignalResponse,
    AgentSignupRequest,
)
from services.agent_service import (
    dhan_order_to_native,
    serialize_agent_bootstrap,
    serialize_agent_profile,
    serialize_dhan_funds,
    serialize_dhan_order,
    serialize_dhan_position,
)
from services.auth_service import bootstrap_agent_key, signup_agent_key
from services.signal_adapter import signal_adapter
from services.trading_service import (
    _position_unrealized,
    cancel_order,
    close_all_positions,
    close_position,
    funds_summary,
    get_order,
    list_orders,
    list_positions,
    place_order,
)


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/agent", tags=["agent"])


def _prepare_secret_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _ensure_agent_portfolio(key, portfolio_id: str) -> str:
    if key.portfolio_id != portfolio_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Portfolio not allowed for this API key")
    return portfolio_id


def _load_agent_context(db: Session, key) -> tuple[User, Portfolio]:
    owner = db.query(User).filter(User.id == key.user_id, User.is_active.is_(True)).first()
    portfolio = db.query(Portfolio).filter(Portfolio.id == key.portfolio_id, Portfolio.user_id == key.user_id).first()
    if not owner or not portfolio:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Agent key owner not found")
    return owner, portfolio


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


@router.post("/bootstrap", response_model=AgentBootstrapResponse)
def agent_bootstrap(
    payload: AgentBootstrapRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("agent:bootstrap", 10, 60)),
):
    _prepare_secret_response(response)
    user, portfolio, key, secret = bootstrap_agent_key(db, payload)
    return serialize_agent_bootstrap(db, user=user, portfolio=portfolio, key=key, secret=secret)


@router.post("/signup", response_model=AgentBootstrapResponse)
def agent_signup(
    payload: AgentSignupRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("agent:signup", 5, 60)),
):
    _prepare_secret_response(response)
    user, portfolio, key, secret = signup_agent_key(db, payload)
    return serialize_agent_bootstrap(db, user=user, portfolio=portfolio, key=key, secret=secret)


@router.get("/me", response_model=AgentProfileResponse)
def agent_me(
    db: Session = Depends(get_db),
    key=Depends(get_agent_key),
):
    owner, portfolio = _load_agent_context(db, key)
    return serialize_agent_profile(db, user=owner, portfolio=portfolio, key=key)


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


@router.get("/orders/{order_id}", response_model=OrderSummary)
def agent_order_detail(
    order_id: str,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("orders:read")),
):
    return OrderSummary.model_validate(get_order(db, order_id, portfolio_id=key.portfolio_id))


@router.post("/orders/{order_id}/cancel", response_model=OrderSummary)
def agent_cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("orders:write")),
    _: None = Depends(rate_limit("agent:cancel", 120, 60)),
):
    order = cancel_order(db, order_id, portfolio_id=key.portfolio_id, actor_type="agent", actor_id=key.id)
    return OrderSummary.model_validate(order)


@router.get("/positions", response_model=list[PositionSummary])
def agent_positions(db: Session = Depends(get_db), key=Depends(require_agent_scope("positions:read"))):
    return [_serialize_position(position) for position in list_positions(db, key.portfolio_id)]


@router.post("/positions/square-off", response_model=list[OrderSummary])
def agent_square_off_all(
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("positions:write")),
    _: None = Depends(rate_limit("agent:square-off-all", 60, 60)),
):
    return [
        OrderSummary.model_validate(order)
        for order in close_all_positions(db, key.portfolio_id, actor_type="agent", actor_id=key.id)
    ]


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


@router.post("/positions/{position_id}/square-off", response_model=OrderSummary)
def agent_square_off_position(
    position_id: str,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("positions:write")),
    _: None = Depends(rate_limit("agent:close-alias", 120, 60)),
):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position or position.portfolio_id != key.portfolio_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    order = close_position(db, position_id, actor_type="agent", actor_id=key.id)
    return OrderSummary.model_validate(order)


@router.get("/funds", response_model=FundsResponse)
def agent_funds_self(db: Session = Depends(get_db), key=Depends(require_agent_scope("funds:read"))):
    return funds_summary(db, key.portfolio_id)


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


@router.get("/dhan/fundlimit", response_model=DhanFundResponse)
def agent_dhan_funds(
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("funds:read")),
):
    return serialize_dhan_funds(db, key.portfolio_id)


@router.get("/dhan/positions", response_model=list[DhanPositionResponse])
def agent_dhan_positions(
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("positions:read")),
):
    return [serialize_dhan_position(position) for position in list_positions(db, key.portfolio_id)]


@router.get("/dhan/orders", response_model=list[DhanOrderResponse])
def agent_dhan_orders(
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("orders:read")),
):
    return [serialize_dhan_order(order) for order in list_orders(db, key.portfolio_id)]


@router.get("/dhan/orders/{order_id}", response_model=DhanOrderResponse)
def agent_dhan_order_detail(
    order_id: str,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("orders:read")),
):
    return serialize_dhan_order(get_order(db, order_id, portfolio_id=key.portfolio_id))


@router.post("/dhan/orders", response_model=DhanOrderResponse)
def agent_dhan_order(
    payload: DhanOrderRequest,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("orders:write")),
    _: None = Depends(rate_limit("agent:dhan-orders", 120, 60)),
):
    order = place_order(
        db,
        dhan_order_to_native(payload, key.portfolio_id),
        actor_type="agent",
        actor_id=key.id,
        source="agent",
    )
    return serialize_dhan_order(order)


@router.delete("/dhan/orders/{order_id}", response_model=DhanOrderResponse)
def agent_dhan_cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("orders:write")),
    _: None = Depends(rate_limit("agent:dhan-cancel", 120, 60)),
):
    order = cancel_order(db, order_id, portfolio_id=key.portfolio_id, actor_type="agent", actor_id=key.id)
    return serialize_dhan_order(order)


@router.post("/dhan/positions/{position_id}/exit", response_model=DhanOrderResponse)
def agent_dhan_exit_position(
    position_id: str,
    db: Session = Depends(get_db),
    key=Depends(require_agent_scope("positions:write")),
    _: None = Depends(rate_limit("agent:dhan-exit", 120, 60)),
):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position or position.portfolio_id != key.portfolio_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    order = close_position(db, position_id, actor_type="agent", actor_id=key.id)
    return serialize_dhan_order(order)
