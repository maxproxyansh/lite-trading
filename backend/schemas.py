from __future__ import annotations

import ipaddress
from urllib.parse import urlparse
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


Role = Literal["admin", "trader", "viewer"]
OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT", "SL", "SL-M"]
BracketEntryOrderType = Literal["MARKET", "LIMIT"]
OrderProduct = Literal["NRML", "MIS"]
OrderValidity = Literal["DAY"]
OrderSort = Literal["asc", "desc"]
OrderLinkType = Literal["ENTRY", "STOP_LOSS", "TARGET"]
AlertDirection = Literal["ABOVE", "BELOW"]
AlertStatus = Literal["ACTIVE", "TRIGGERED", "CANCELLED"]
AgentEventType = Literal["alert.triggered"]
PortfolioKind = Literal["manual", "agent"]
ExchangeSegment = Literal["NSE_FNO"]
WebhookEvent = Literal["order.filled", "order.cancelled", "position.opened", "position.closed", "alert.triggered"]
PcrScope = Literal["all_loaded_strikes_for_active_expiry"]


def default_agent_scopes() -> list[str]:
    return [
        "orders:read",
        "orders:write",
        "positions:read",
        "positions:write",
        "alerts:read",
        "alerts:write",
        "events:read",
        "events:write",
        "signals:read",
        "signals:write",
        "funds:read",
    ]


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    api_prefix: str | None = None
    meta_url: str | None = None
    docs_url: str | None = None
    openapi_url: str | None = None
    redoc_url: str | None = None


class WebSocketEventMeta(BaseModel):
    type: str
    description: str


class HumanAuthMeta(BaseModel):
    mode: Literal["jwt_bearer"] = "jwt_bearer"
    recommended_for_agents: bool = False
    login_path: str
    refresh_path: str
    access_token_expires_in_seconds: int


class AgentAuthMeta(BaseModel):
    mode: Literal["api_key"] = "api_key"
    recommended_for_agents: bool = True
    header: str = "X-API-Key"
    bootstrap_path: str
    signup_path: str
    default_key_expires_in_days: int
    rotation_supported: bool = True


class AuthContractMeta(BaseModel):
    human: HumanAuthMeta
    agent: AgentAuthMeta


class WebSocketMeta(BaseModel):
    path: str
    url: str
    auth_header: str = "X-API-Key"
    ping_message: str = "ping"
    pong_message: str = "pong"
    events: list[WebSocketEventMeta]


class MarketDataContractMeta(BaseModel):
    pcr_scope: PcrScope = "all_loaded_strikes_for_active_expiry"
    pcr_description: str


class ApiMetaResponse(BaseModel):
    app: str
    version: str
    api_prefix: str
    base_url: str
    meta_url: str
    docs_url: str
    openapi_url: str
    redoc_url: str | None = None
    websocket: WebSocketMeta
    auth: AuthContractMeta
    market_data: MarketDataContractMeta
    links: dict[str, str]


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
    day_high: float | None = None
    day_low: float | None = None
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
    day_high: float | None = None
    day_low: float | None = None
    vix: float | None = None
    pcr: float | None = None
    pcr_scope: PcrScope = "all_loaded_strikes_for_active_expiry"
    call_oi_total: float = 0.0
    put_oi_total: float = 0.0
    market_status: str
    expiries: list[str] = Field(default_factory=list)
    active_expiry: str | None = None
    degraded: bool = False
    degraded_reason: str | None = None
    updated_at: datetime


class OptionChainResponse(BaseModel):
    snapshot: MarketSnapshot
    rows: list[OptionChainRow]


class DhanProviderHealth(BaseModel):
    provider: Literal["dhan"] = "dhan"
    configured: bool
    authority_mode: Literal["lite"] = "lite"
    p0_status: Literal["ok", "critical"]
    incident_open: bool = False
    incident_class: str | None = None
    incident_fingerprint: str | None = None
    incident_reason: str | None = None
    incident_message: str | None = None
    incident_since: datetime | None = None
    affected_consumers: list[str] = Field(default_factory=list)
    token_source: str | None = None
    token_expires_at: datetime | None = None
    last_token_refresh_at: datetime | None = None
    last_profile_check_at: datetime | None = None
    last_lease_issued_at: datetime | None = None
    last_rest_success_at: datetime | None = None
    last_option_chain_success_at: datetime | None = None
    last_feed_message_at: datetime | None = None
    last_market_data_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_reason: str | None = None
    last_error_message: str | None = None
    data_plan_status: str | None = None
    data_valid_until: datetime | None = None
    realtime_stale_after_seconds: int
    chain_stale_after_seconds: int
    renewal_lead_seconds: int
    feed_connected: bool = False
    market_open: bool = False
    slack_configured: bool = False
    totp_regeneration_enabled: bool = False
    consumer_states: list["DhanConsumerStateSummary"] = Field(default_factory=list)


class DhanConsumerStateSummary(BaseModel):
    consumer: str
    instance_id: str
    state: str
    reason: str | None = None
    message: str | None = None
    observed_at: datetime
    generation: int | None = None


class DhanLeaseResponse(BaseModel):
    client_id: str
    access_token: str
    expires_at: datetime | None = None
    generation: int
    validated_at: datetime | None = None
    token_source: str | None = None
    data_plan_status: str | None = None
    data_valid_until: datetime | None = None


class DhanConsumerStateUpdateRequest(BaseModel):
    consumer: str = Field(min_length=1, max_length=64)
    instance_id: str = Field(min_length=1, max_length=128)
    state: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=128)
    message: str | None = Field(default=None, max_length=2000)
    observed_at: datetime
    generation: int | None = None


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


class AlertUpdateRequest(BaseModel):
    target_price: float = Field(gt=0)
    direction: AlertDirection | None = None


class AlertSummary(BaseModel):
    id: str
    portfolio_id: str | None = None
    symbol: str
    target_price: float
    direction: AlertDirection
    status: AlertStatus
    last_price: float | None = None
    created_at: datetime
    updated_at: datetime
    triggered_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentEventSource(BaseModel):
    type: Literal["alert"]
    id: str


class AgentEventEnvelope(BaseModel):
    id: str
    type: AgentEventType
    occurred_at: datetime
    user_id: str
    portfolio_id: str
    agent_key_id: str
    source: AgentEventSource
    data: dict[str, Any]
    claimed_at: datetime | None = None
    claim_expires_at: datetime | None = None
    acked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None


class AgentEventClaimRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)
    lease_seconds: int = Field(default=30, ge=5, le=300)
    types: list[AgentEventType] | None = None


class AgentEventFailRequest(BaseModel):
    error: str = Field(min_length=1, max_length=1000)
    retry_delay_seconds: int = Field(default=0, ge=0, le=300)


class AgentWebhookCreateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=1024)
    events: list[WebhookEvent] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_target(self):
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Webhook URL must be a valid http or https URL")
        hostname = parsed.hostname or ""
        if hostname == "localhost" or hostname.endswith(".local"):
            raise ValueError("Webhook URL host is not allowed")
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            ip = None
        if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved):
            raise ValueError("Webhook URL host is not allowed")
        deduped: list[WebhookEvent] = []
        for event in self.events:
            if event not in deduped:
                deduped.append(event)
        self.events = deduped
        return self


class AgentWebhookSummary(BaseModel):
    id: str
    agent_key_id: str
    portfolio_id: str
    url: str
    events: list[WebhookEvent]
    last_delivery_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentWebhookCreateResponse(AgentWebhookSummary):
    secret: str


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


class OrderModifyRequest(BaseModel):
    quantity: int | None = None
    price: float | None = None
    trigger_price: float | None = None


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
    parent_order_id: str | None = None
    link_type: OrderLinkType | None = None
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


class OrderListResponse(BaseModel):
    items: list[OrderSummary]
    total: int
    offset: int
    limit: int


class BracketOrderRequest(BaseModel):
    portfolio_id: str
    symbol: str | None = None
    expiry: str
    strike: int
    option_type: Literal["CE", "PE"]
    side: OrderSide
    product: OrderProduct = "NRML"
    validity: OrderValidity = "DAY"
    lots: int = Field(default=1, ge=1, le=200)
    entry_order_type: BracketEntryOrderType = "LIMIT"
    entry_price: float | None = Field(default=None, gt=0)
    stop_loss_price: float = Field(gt=0)
    stop_loss_trigger_price: float = Field(gt=0)
    target_price: float = Field(gt=0)
    idempotency_key: str | None = None

    @model_validator(mode="after")
    def validate_prices(self):
        if self.entry_order_type == "LIMIT" and self.entry_price is None:
            raise ValueError("entry_price is required for LIMIT bracket entries")
        if self.entry_order_type == "MARKET" and self.entry_price is not None:
            raise ValueError("entry_price is not allowed for MARKET bracket entries")
        return self


class BracketOrderResponse(BaseModel):
    parent: OrderSummary
    stop_loss: OrderSummary
    target: OrderSummary


class OrderModifyRequest(BaseModel):
    price: float | None = Field(default=None, gt=0)
    trigger_price: float | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_any_field(self):
        if self.price is None and self.trigger_price is None and self.quantity is None:
            raise ValueError("At least one of price, trigger_price, or quantity is required")
        return self


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


class DetailedTradeSummary(BaseModel):
    symbol: str
    strike: int
    option_type: Literal["CE", "PE"]
    direction: Literal["LONG", "SHORT"]
    quantity: int
    lots: int
    entry_time: datetime
    exit_time: datetime
    hold_seconds: float
    hold_days: int
    realized_pnl: float
    entry_price: float
    exit_price: float
    expiry_date: str
    days_to_expiry_at_entry: int
    days_to_expiry_at_exit: int
    spot_at_entry: float | None = None
    spot_at_exit: float | None = None
    vix_at_entry: float | None = None
    vix_at_exit: float | None = None
    atm_distance: int | None = None


class AnalyticsAttribution(BaseModel):
    symbol: str
    strike: int
    option_type: Literal["CE", "PE"]
    direction: Literal["LONG", "SHORT"]
    closed_trades: int
    realized_pnl: float


class DetailedAnalyticsResponse(BaseModel):
    portfolio_id: str
    from_date: date | None = None
    to_date: date | None = None
    total_closed_trades: int
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float
    trade_attribution: list[AnalyticsAttribution]
    closed_trades: list[DetailedTradeSummary]
    drawdown_curve: list[AnalyticsPoint]
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    win_loss_distribution: list[AnalyticsPoint]
    average_hold_seconds: float
    max_consecutive_wins: int
    max_consecutive_losses: int


class EnrichedAnalyticsResponse(BaseModel):
    portfolio_id: str
    total_closed_trades: int
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float
    win_rate: float
    expectancy: float
    risk_reward: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    biggest_win: float
    biggest_loss: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_hold_seconds: float
    avg_win_hold_seconds: float
    avg_loss_hold_seconds: float
    equity_curve: list[AnalyticsPoint]
    pnl_by_day: list[AnalyticsPoint]
    drawdown_curve: list[AnalyticsPoint]
    closed_trades: list[DetailedTradeSummary]


class WebsocketEnvelope(BaseModel):
    type: str
    payload: dict[str, Any]


class ParticipantPositions(BaseModel):
    fut_long: int
    fut_short: int
    net_futures: int
    opt_call_long: int
    opt_call_short: int
    opt_put_long: int
    opt_put_short: int


class ParticipantSnapshot(BaseModel):
    date: date
    fii: ParticipantPositions
    dii: ParticipantPositions
    pro: ParticipantPositions
    client: ParticipantPositions


class ParticipantHistoryResponse(BaseModel):
    snapshots: list[ParticipantSnapshot]


class WebAuthnRegisterOptionsResponse(BaseModel):
    options: dict


class WebAuthnRegisterRequest(BaseModel):
    credential: dict


class WebAuthnAuthenticateOptionsRequest(BaseModel):
    email: str


class WebAuthnAuthenticateOptionsResponse(BaseModel):
    options: dict


class WebAuthnAuthenticateRequest(BaseModel):
    credential: dict
    email: str


AgentProfileResponse.model_rebuild()
AgentBootstrapResponse.model_rebuild()
