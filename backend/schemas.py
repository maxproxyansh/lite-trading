from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


Role = Literal["admin", "trader", "viewer"]
OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT", "SL", "SL-M"]
OrderProduct = Literal["NRML", "MIS"]
OrderValidity = Literal["DAY"]
AlertDirection = Literal["ABOVE", "BELOW"]
AlertStatus = Literal["ACTIVE", "TRIGGERED", "CANCELLED"]
PortfolioKind = Literal["manual", "agent"]
ExchangeSegment = Literal["NSE_FNO"]


def default_agent_scopes() -> list[str]:
    return [
        "orders:read",
        "orders:write",
        "positions:read",
        "positions:write",
        "signals:read",
        "signals:write",
        "funds:read",
    ]


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class UserSummary(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: Role
    is_active: bool

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenEnvelope(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary


class SignupRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)


class CreateUserRequest(BaseModel):
    email: EmailStr
    display_name: str
    password: str = Field(min_length=8)
    role: Role = "trader"


class CreateAgentKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    portfolio_id: str
    scopes: list[str] = Field(default_factory=default_agent_scopes)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)
    rotate_existing: bool = True


class AgentKeyResponse(BaseModel):
    id: str
    user_id: str
    portfolio_id: str
    name: str
    key_prefix: str
    scopes: list[str]
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    secret: str | None = None


class AgentBootstrapRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    agent_name: str = Field(min_length=1, max_length=100)
    portfolio_kind: PortfolioKind = "agent"
    scopes: list[str] = Field(default_factory=default_agent_scopes)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)
    rotate_existing: bool = True


class AgentSignupRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    agent_name: str = Field(min_length=1, max_length=100)
    portfolio_kind: PortfolioKind = "agent"
    scopes: list[str] = Field(default_factory=default_agent_scopes)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)
    rotate_existing: bool = True


class AgentProfileResponse(BaseModel):
    owner: UserSummary
    portfolio: "PortfolioSummary"
    agent: AgentKeyResponse
    links: dict[str, str]


class AgentBootstrapResponse(BaseModel):
    owner: UserSummary
    portfolio: "PortfolioSummary"
    agent: AgentKeyResponse
    api_key: str
    links: dict[str, str]


class MarketDepthLevel(BaseModel):
    price: float
    quantity: int


class OptionQuote(BaseModel):
    symbol: str
    security_id: str | None = None
    strike: int
    option_type: Literal["CE", "PE"]
    expiry: str
    ltp: float
    bid: float | None = None
    ask: float | None = None
    bid_qty: int | None = None
    ask_qty: int | None = None
    iv: float | None = None
    oi: float | None = None
    oi_lakhs: float | None = None
    volume: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None


class OptionChainRow(BaseModel):
    strike: int
    is_atm: bool
    call: OptionQuote
    put: OptionQuote


class MarketSnapshot(BaseModel):
    spot_symbol: str = "NIFTY 50"
    spot: float
    change: float
    change_pct: float
    vix: float | None = None
    pcr: float | None = None
    market_status: str
    expiries: list[str] = Field(default_factory=list)
    active_expiry: str | None = None
    degraded: bool = False
    degraded_reason: str | None = None
    updated_at: datetime


class OptionChainResponse(BaseModel):
    snapshot: MarketSnapshot
    rows: list[OptionChainRow]


class Candle(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0


class CandleResponse(BaseModel):
    timeframe: str
    candles: list[Candle]
    source: str
    degraded: bool = False
    has_more: bool = False
    next_before: int | None = None


class AlertCreateRequest(BaseModel):
    symbol: str = "NIFTY 50"
    target_price: float = Field(gt=0)
    direction: AlertDirection | None = None


class AlertSummary(BaseModel):
    id: str
    symbol: str
    target_price: float
    direction: AlertDirection
    status: AlertStatus
    last_price: float | None = None
    created_at: datetime
    updated_at: datetime
    triggered_at: datetime | None = None

    model_config = {"from_attributes": True}


class SignalResponse(BaseModel):
    id: str
    source: str
    direction: str
    confidence_label: str
    confidence_score: float
    trade_text: str | None = None
    strike: int | None = None
    option_type: Literal["CE", "PE"] | None = None
    expiry: str | None = None
    entry_low: float | None = None
    entry_high: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    index_target: float | None = None
    index_stop: float | None = None
    is_actionable: bool
    target_valid: bool
    stop_valid: bool
    generated_at: datetime

    model_config = {"from_attributes": True}


class SignalIngestRequest(BaseModel):
    payload: dict[str, Any]


class PortfolioSummary(BaseModel):
    id: str
    kind: PortfolioKind
    name: str
    description: str | None = None
    starting_cash: float
    cash_balance: float
    blocked_margin: float
    blocked_premium: float
    realized_pnl: float
    available_funds: float
    total_equity: float


class OrderRequest(BaseModel):
    portfolio_id: str
    symbol: str | None = None
    expiry: str
    strike: int
    option_type: Literal["CE", "PE"]
    side: OrderSide
    order_type: OrderType
    product: OrderProduct = "NRML"
    validity: OrderValidity = "DAY"
    lots: int = Field(default=1, ge=1, le=200)
    price: float | None = None
    trigger_price: float | None = None
    signal_id: str | None = None
    idempotency_key: str | None = None

    @model_validator(mode="after")
    def validate_order_prices(self):
        if self.order_type in {"LIMIT", "SL"}:
            if self.price is None or self.price <= 0:
                raise ValueError("price is required for LIMIT and SL orders")
        elif self.price is not None and self.price <= 0:
            raise ValueError("price must be positive when provided")

        if self.order_type in {"SL", "SL-M"}:
            if self.trigger_price is None or self.trigger_price <= 0:
                raise ValueError("trigger_price is required for SL and SL-M orders")
        elif self.trigger_price is not None and self.trigger_price <= 0:
            raise ValueError("trigger_price must be positive when provided")

        return self


class OrderSummary(BaseModel):
    id: str
    portfolio_id: str
    symbol: str
    expiry: str
    strike: int
    option_type: Literal["CE", "PE"]
    side: OrderSide
    order_type: OrderType
    product: OrderProduct
    validity: OrderValidity
    lots: int
    quantity: int
    price: float | None = None
    trigger_price: float | None = None
    status: str
    average_price: float | None = None
    filled_quantity: int
    premium_required: float
    margin_required: float
    charges: float
    message: str | None = None
    source: str
    requested_at: datetime
    filled_at: datetime | None = None

    model_config = {"from_attributes": True}


class PositionSummary(BaseModel):
    id: str
    portfolio_id: str
    symbol: str
    expiry: str
    strike: int
    option_type: Literal["CE", "PE"]
    product: OrderProduct
    net_quantity: int
    lot_size: int
    average_open_price: float
    last_price: float
    blocked_margin: float
    realized_pnl: float
    unrealized_pnl: float
    opened_at: datetime

    model_config = {"from_attributes": True}


class FundsResponse(BaseModel):
    portfolio_id: str
    cash_balance: float
    blocked_margin: float
    blocked_premium: float
    available_funds: float
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float


class DhanOrderRequest(BaseModel):
    transaction_type: OrderSide
    quantity: int = Field(ge=1)
    exchange_segment: ExchangeSegment = "NSE_FNO"
    product_type: OrderProduct = "NRML"
    order_type: OrderType
    validity: OrderValidity = "DAY"
    trading_symbol: str | None = None
    security_id: str | None = None
    expiry: str | None = None
    strike: int | None = None
    option_type: Literal["CE", "PE"] | None = None
    price: float | None = None
    trigger_price: float | None = None
    correlationId: str | None = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_instrument(self):
        has_symbol = bool(self.trading_symbol or self.security_id)
        has_parts = self.expiry is not None and self.strike is not None and self.option_type is not None
        if not has_symbol and not has_parts:
            raise ValueError("Provide trading_symbol, security_id, or expiry/strike/option_type")
        if not self.correlationId:
            raise ValueError("correlationId is required for agent orders")
        return self


class DhanOrderResponse(BaseModel):
    order_id: str = Field(alias="orderId")
    order_status: str = Field(alias="orderStatus")
    transaction_type: OrderSide = Field(alias="transactionType")
    exchange_segment: ExchangeSegment = Field(default="NSE_FNO", alias="exchangeSegment")
    trading_symbol: str = Field(alias="tradingSymbol")
    security_id: str | None = Field(default=None, alias="securityId")
    quantity: int
    filled_qty: int = Field(alias="filledQty")
    price: float | None = None
    trigger_price: float | None = Field(default=None, alias="triggerPrice")
    average_traded_price: float | None = Field(default=None, alias="averageTradedPrice")
    product_type: OrderProduct = Field(alias="productType")
    order_type: OrderType = Field(alias="orderType")
    validity: OrderValidity
    correlation_id: str | None = Field(default=None, alias="correlationId")
    message: str | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class DhanPositionResponse(BaseModel):
    position_id: str = Field(alias="positionId")
    trading_symbol: str = Field(alias="tradingSymbol")
    security_id: str | None = Field(default=None, alias="securityId")
    product_type: OrderProduct = Field(alias="productType")
    quantity: int
    buy_avg: float = Field(alias="buyAvg")
    sell_avg: float = Field(alias="sellAvg")
    last_price: float = Field(alias="lastPrice")
    realized_profit: float = Field(alias="realizedProfit")
    unrealized_profit: float = Field(alias="unrealizedProfit")
    blocked_margin: float = Field(alias="blockedMargin")
    expiry: str
    strike: int
    option_type: Literal["CE", "PE"] = Field(alias="optionType")

    model_config = {"populate_by_name": True}


class DhanFundResponse(BaseModel):
    account_id: str = Field(alias="accountId")
    available_balance: float = Field(alias="availableBalance")
    cash_balance: float = Field(alias="cashBalance")
    utilized_margin: float = Field(alias="utilizedMargin")
    blocked_premium: float = Field(alias="blockedPremium")
    realized_pnl: float = Field(alias="realizedPnl")
    unrealized_pnl: float = Field(alias="unrealizedPnl")
    total_equity: float = Field(alias="totalEquity")

    model_config = {"populate_by_name": True}


class AnalyticsPoint(BaseModel):
    label: str
    value: float


class AnalyticsResponse(BaseModel):
    portfolio_id: str
    total_orders: int
    filled_orders: int
    win_rate: float
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float
    equity_curve: list[AnalyticsPoint]
    pnl_by_day: list[AnalyticsPoint]


class WebsocketEnvelope(BaseModel):
    type: str
    payload: dict[str, Any]


AgentProfileResponse.model_rebuild()
AgentBootstrapResponse.model_rebuild()
