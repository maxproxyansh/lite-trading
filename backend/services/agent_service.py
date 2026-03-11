from __future__ import annotations

import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from models import AgentApiKey, Order, Portfolio, Position, User
from schemas import (
    AgentBootstrapResponse,
    AgentKeyResponse,
    AgentProfileResponse,
    DhanFundResponse,
    DhanOrderRequest,
    DhanOrderResponse,
    DhanPositionResponse,
    OrderRequest,
    PortfolioSummary,
    UserSummary,
)
from services.market_data import market_data_service
from services.trading_service import _position_unrealized, funds_summary, portfolio_summary


settings = get_settings()
LOT_SIZE = settings.nifty_lot_size
OPTION_SYMBOL_PATTERN = re.compile(r"^(?P<root>[A-Z0-9]+)_(?P<expiry>\d{4}-\d{2}-\d{2})_(?P<strike>\d+)_(?P<option_type>CE|PE)$")


def agent_links() -> dict[str, str]:
    prefix = settings.api_prefix
    return {
        "profile": f"{prefix}/agent/me",
        "orders": f"{prefix}/agent/orders",
        "positions": f"{prefix}/agent/positions",
        "funds": f"{prefix}/agent/funds",
        "signals": f"{prefix}/agent/signals",
        "bootstrap": f"{prefix}/agent/bootstrap",
        "signup": f"{prefix}/agent/signup",
        "square_off_all": f"{prefix}/agent/positions/square-off",
        "dhan_orders": f"{prefix}/agent/dhan/orders",
        "dhan_positions": f"{prefix}/agent/dhan/positions",
        "dhan_funds": f"{prefix}/agent/dhan/fundlimit",
    }


def serialize_agent_key(key: AgentApiKey, *, secret: str | None = None) -> AgentKeyResponse:
    return AgentKeyResponse(
        id=key.id,
        user_id=key.user_id,
        portfolio_id=key.portfolio_id,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=list(key.scopes or []),
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        secret=secret,
    )


def _portfolio_summary(db: Session, portfolio: Portfolio) -> PortfolioSummary:
    return PortfolioSummary(**portfolio_summary(db, portfolio))


def serialize_agent_profile(db: Session, *, user: User, portfolio: Portfolio, key: AgentApiKey) -> AgentProfileResponse:
    return AgentProfileResponse(
        owner=UserSummary.model_validate(user),
        portfolio=_portfolio_summary(db, portfolio),
        agent=serialize_agent_key(key),
        links=agent_links(),
    )


def serialize_agent_bootstrap(
    db: Session,
    *,
    user: User,
    portfolio: Portfolio,
    key: AgentApiKey,
    secret: str,
) -> AgentBootstrapResponse:
    return AgentBootstrapResponse(
        owner=UserSummary.model_validate(user),
        portfolio=_portfolio_summary(db, portfolio),
        agent=serialize_agent_key(key),
        api_key=secret,
        links=agent_links(),
    )


def _lookup_security_id(security_id: str) -> dict | None:
    for quote in market_data_service.quotes.values():
        if str(quote.get("security_id") or "") == str(security_id):
            return quote
    return None


def _parse_symbol(symbol: str) -> tuple[str, int, str]:
    match = OPTION_SYMBOL_PATTERN.fullmatch(symbol)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported trading_symbol format. Expected ROOT_YYYY-MM-DD_STRIKE_CE|PE",
        )
    return match.group("expiry"), int(match.group("strike")), match.group("option_type")


def _resolve_order_inputs(payload: DhanOrderRequest) -> tuple[str, str, int, str, str | None]:
    if payload.trading_symbol:
        expiry, strike, option_type = _parse_symbol(payload.trading_symbol)
        quote = market_data_service.get_quote(payload.trading_symbol)
        security_id = str(quote.get("security_id")) if quote and quote.get("security_id") else None
        return payload.trading_symbol, expiry, strike, option_type, security_id

    if payload.security_id:
        quote = _lookup_security_id(payload.security_id)
        if not quote:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SECURITY_ID_NOT_AVAILABLE")
        symbol = str(quote.get("symbol") or "")
        if not symbol:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MARKET_DATA_UNAVAILABLE")
        expiry = str(quote.get("expiry") or payload.expiry or "")
        strike = int(quote.get("strike") or payload.strike or 0)
        option_type = str(quote.get("option_type") or payload.option_type or "")
        if not expiry or strike <= 0 or option_type not in {"CE", "PE"}:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="QUOTE_METADATA_INCOMPLETE")
        return symbol, expiry, strike, option_type, str(payload.security_id)

    symbol = market_data_service.resolve_symbol(
        expiry=payload.expiry or "",
        strike=payload.strike or 0,
        option_type=payload.option_type or "",
    )
    return symbol, payload.expiry or "", int(payload.strike or 0), str(payload.option_type or ""), None


def dhan_order_to_native(payload: DhanOrderRequest, portfolio_id: str) -> OrderRequest:
    if payload.quantity % LOT_SIZE != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quantity must be a multiple of {LOT_SIZE} for NIFTY option orders",
        )
    symbol, expiry, strike, option_type, _security_id = _resolve_order_inputs(payload)
    return OrderRequest(
        portfolio_id=portfolio_id,
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        option_type=option_type,
        side=payload.transaction_type,
        order_type=payload.order_type,
        product=payload.product_type,
        validity=payload.validity,
        lots=max(payload.quantity // LOT_SIZE, 1),
        price=payload.price,
        trigger_price=payload.trigger_price,
        idempotency_key=payload.correlation_id,
    )


def serialize_dhan_order(order: Order) -> DhanOrderResponse:
    return DhanOrderResponse(
        orderId=order.id,
        orderStatus=order.status,
        transactionType=order.side,
        exchangeSegment="NSE_FNO",
        tradingSymbol=order.symbol,
        securityId=order.security_id,
        quantity=order.quantity,
        filledQty=order.filled_quantity,
        price=float(order.price) if order.price is not None else None,
        triggerPrice=float(order.trigger_price) if order.trigger_price is not None else None,
        averageTradedPrice=float(order.average_price) if order.average_price is not None else None,
        productType=order.product,
        orderType=order.order_type,
        validity=order.validity,
        correlationId=order.idempotency_key,
        message=order.message,
        createdAt=order.requested_at,
        updatedAt=order.updated_at,
    )


def serialize_dhan_position(position: Position) -> DhanPositionResponse:
    buy_avg = position.average_open_price if position.net_quantity > 0 else 0.0
    sell_avg = position.average_open_price if position.net_quantity < 0 else 0.0
    return DhanPositionResponse(
        positionId=position.id,
        tradingSymbol=position.symbol,
        securityId=position.security_id,
        productType=position.product,
        quantity=position.net_quantity,
        buyAvg=buy_avg,
        sellAvg=sell_avg,
        lastPrice=position.last_price,
        realizedProfit=position.realized_pnl,
        unrealizedProfit=_position_unrealized(position),
        blockedMargin=position.blocked_margin,
        expiry=position.expiry,
        strike=position.strike,
        optionType=position.option_type,
    )


def serialize_dhan_funds(db: Session, portfolio_id: str) -> DhanFundResponse:
    funds = funds_summary(db, portfolio_id)
    return DhanFundResponse(
        accountId=funds.portfolio_id,
        availableBalance=funds.available_funds,
        cashBalance=funds.cash_balance,
        utilizedMargin=funds.blocked_margin,
        blockedPremium=funds.blocked_premium,
        realizedPnl=funds.realized_pnl,
        unrealizedPnl=funds.unrealized_pnl,
        totalEquity=funds.total_equity,
    )
