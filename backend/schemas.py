from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


Role = Literal["admin", "trader", "viewer"]
OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT", "SL", "SL-M"]
OrderProduct = Literal["NRML", "MIS"]
OrderValidity = Literal["DAY"]


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
    name: str
    portfolio_id: str
    scopes: list[str] = Field(
        default_factory=lambda: [
            "orders:read",
            "orders:write",
            "positions:read",
            "positions:write",
            "signals:read",
            "signals:write",
            "funds:read",
        ]
    )


class AgentKeyResponse(BaseModel):
    id: str
    user_id: str
    portfolio_id: str
    name: str
    key_prefix: str
    scopes: list[str]
    secret: str | None = None


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
    kind: Literal["manual", "agent"]
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
