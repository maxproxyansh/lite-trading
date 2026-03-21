from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid4() -> str:
    return str(uuid.uuid4())


class BaseModelMixin:
    id = Column(String(64), primary_key=True, default=uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class User(Base, BaseModelMixin):
    __tablename__ = "users"

    email = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="trader")
    is_active = Column(Boolean, nullable=False, default=True)


class RefreshToken(Base, BaseModelMixin):
    __tablename__ = "refresh_tokens"

    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))


class WebAuthnCredential(Base, BaseModelMixin):
    __tablename__ = "webauthn_credentials"

    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    credential_id = Column(Text, nullable=False, unique=True)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0)
    transports = Column(JSON, nullable=True)


class AgentApiKey(Base, BaseModelMixin):
    __tablename__ = "agent_api_keys"

    name = Column(String(255), nullable=False)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True, index=True)
    portfolio_id = Column(String(64), ForeignKey("portfolios.id"), nullable=True, index=True)
    key_prefix = Column(String(24), nullable=False, unique=True)
    key_hash = Column(String(255), nullable=False, unique=True)
    scopes = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True), index=True)
    revoked_at = Column(DateTime(timezone=True))


class PulseClaimToken(Base, BaseModelMixin):
    __tablename__ = "pulse_claim_tokens"

    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    api_key_id = Column(String(64), ForeignKey("agent_api_keys.id"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    api_secret = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    claimed = Column(Boolean, nullable=False, default=False)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True, index=True)
    kind = Column(String(16), nullable=False, default="manual")
    name = Column(String(255), nullable=False)
    description = Column(Text)
    starting_cash = Column(Numeric(14, 2), nullable=False, default=500000.0)
    cash_balance = Column(Numeric(14, 2), nullable=False, default=500000.0)
    blocked_margin = Column(Numeric(14, 2), nullable=False, default=0.0)
    blocked_premium = Column(Numeric(14, 2), nullable=False, default=0.0)
    realized_pnl = Column(Numeric(14, 2), nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Order(Base, BaseModelMixin):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_portfolio_status", "portfolio_id", "status"),
        Index("ix_orders_portfolio_created_at", "portfolio_id", "created_at"),
    )

    portfolio_id = Column(String(64), ForeignKey("portfolios.id"), nullable=False, index=True)
    symbol = Column(String(128), nullable=False, index=True)
    security_id = Column(String(64), index=True)
    expiry = Column(String(32), nullable=False)
    strike = Column(Integer, nullable=False)
    option_type = Column(String(8), nullable=False)
    side = Column(String(8), nullable=False)
    order_type = Column(String(16), nullable=False)
    product = Column(String(16), nullable=False, default="NRML")
    validity = Column(String(16), nullable=False, default="DAY")
    lots = Column(Integer, nullable=False, default=1)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(14, 2))
    trigger_price = Column(Numeric(14, 2))
    status = Column(String(24), nullable=False, default="PENDING")
    average_price = Column(Numeric(14, 2))
    filled_quantity = Column(Integer, nullable=False, default=0)
    last_price = Column(Numeric(14, 2))
    premium_required = Column(Numeric(14, 2), nullable=False, default=0.0)
    margin_required = Column(Numeric(14, 2), nullable=False, default=0.0)
    charges = Column(Numeric(14, 2), nullable=False, default=0.0)
    message = Column(Text)
    parent_order_id = Column(String(64), ForeignKey("orders.id"), index=True)
    link_type = Column(String(24))
    signal_id = Column(String(64), ForeignKey("signals.id"))
    source = Column(String(24), nullable=False, default="human")
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    filled_at = Column(DateTime(timezone=True))


class Fill(Base, BaseModelMixin):
    __tablename__ = "fills"

    order_id = Column(String(64), ForeignKey("orders.id"), nullable=False, index=True)
    portfolio_id = Column(String(64), ForeignKey("portfolios.id"), nullable=False, index=True)
    symbol = Column(String(128), nullable=False, index=True)
    side = Column(String(8), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(14, 2), nullable=False)
    charges = Column(Numeric(14, 2), nullable=False, default=0.0)
    spot_at_fill = Column(Numeric(14, 2), nullable=True)
    vix_at_fill = Column(Numeric(8, 2), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class Position(Base, BaseModelMixin):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "symbol", "product", name="uq_position_portfolio_symbol_product"),
    )

    portfolio_id = Column(String(64), ForeignKey("portfolios.id"), nullable=False, index=True)
    symbol = Column(String(128), nullable=False)
    security_id = Column(String(64), index=True)
    expiry = Column(String(32), nullable=False)
    strike = Column(Integer, nullable=False)
    option_type = Column(String(8), nullable=False)
    product = Column(String(16), nullable=False, default="NRML")
    net_quantity = Column(Integer, nullable=False, default=0)
    lot_size = Column(Integer, nullable=False, default=65)
    average_open_price = Column(Numeric(14, 2), nullable=False, default=0.0)
    last_price = Column(Numeric(14, 2), nullable=False, default=0.0)
    blocked_margin = Column(Numeric(14, 2), nullable=False, default=0.0)
    realized_pnl = Column(Numeric(14, 2), nullable=False, default=0.0)
    opened_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(String(64), primary_key=True)
    source = Column(String(64), nullable=False, default="auto_trader")
    direction = Column(String(24), nullable=False, default="NEUTRAL")
    confidence_label = Column(String(24), nullable=False, default="LOW")
    confidence_score = Column(Float, nullable=False, default=0.0)
    trade_text = Column(String(255))
    strike = Column(Integer)
    option_type = Column(String(8))
    expiry = Column(String(32))
    entry_low = Column(Float)
    entry_high = Column(Float)
    target_price = Column(Float)
    stop_loss = Column(Float)
    index_target = Column(Float)
    index_stop = Column(Float)
    is_actionable = Column(Boolean, nullable=False, default=False)
    target_valid = Column(Boolean, nullable=False, default=False)
    stop_valid = Column(Boolean, nullable=False, default=False)
    raw_payload = Column(JSON, nullable=False, default=dict)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    imported_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class Alert(Base, BaseModelMixin):
    __tablename__ = "alerts"

    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    portfolio_id = Column(String(64), ForeignKey("portfolios.id"), index=True)
    creator_agent_key_id = Column(String(64), ForeignKey("agent_api_keys.id"), index=True)
    symbol = Column(String(128), nullable=False, index=True, default="NIFTY 50")
    target_price = Column(Numeric(14, 2), nullable=False)
    direction = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="ACTIVE")
    last_price = Column(Numeric(14, 2))
    triggered_at = Column(DateTime(timezone=True))


class AgentEvent(Base, BaseModelMixin):
    __tablename__ = "agent_events"
    __table_args__ = (
        Index("ix_agent_events_agent_pending", "agent_key_id", "acked_at", "claim_expires_at", "created_at"),
        Index("ix_agent_events_agent_type", "agent_key_id", "event_type"),
    )

    agent_key_id = Column(String(64), ForeignKey("agent_api_keys.id"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    portfolio_id = Column(String(64), ForeignKey("portfolios.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    source_type = Column(String(32), nullable=False)
    source_id = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    claimed_at = Column(DateTime(timezone=True))
    claim_expires_at = Column(DateTime(timezone=True), index=True)
    acked_at = Column(DateTime(timezone=True), index=True)
    last_error = Column(Text)


class DailyStat(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "date", name="uq_daily_stat_portfolio_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(String(64), ForeignKey("portfolios.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    opening_balance = Column(Numeric(14, 2), nullable=False)
    closing_balance = Column(Numeric(14, 2), nullable=False)
    realized_pnl = Column(Numeric(14, 2), nullable=False, default=0.0)
    unrealized_pnl = Column(Numeric(14, 2), nullable=False, default=0.0)
    trades_count = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)


class AgentWebhook(Base, BaseModelMixin):
    __tablename__ = "agent_webhooks"

    agent_key_id = Column(String(64), ForeignKey("agent_api_keys.id"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    portfolio_id = Column(String(64), ForeignKey("portfolios.id"), nullable=False, index=True)
    url = Column(String(1024), nullable=False)
    events = Column(JSON, nullable=False, default=list)
    secret_salt = Column(String(128), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_delivery_at = Column(DateTime(timezone=True))
    last_failure_at = Column(DateTime(timezone=True))
    last_error = Column(Text)


class WebhookDelivery(Base, BaseModelMixin):
    __tablename__ = "webhook_deliveries"

    webhook_id = Column(String(64), ForeignKey("agent_webhooks.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), index=True, default=utcnow)
    delivered_at = Column(DateTime(timezone=True))
    last_error = Column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_type = Column(String(24), nullable=False)
    actor_id = Column(String(64))
    action = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64))
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ServiceCredential(Base, BaseModelMixin):
    __tablename__ = "service_credentials"

    provider = Column(String(64), nullable=False, unique=True, index=True)
    client_id = Column(String(64), nullable=False)
    access_token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), index=True)
    token_source = Column(String(32), nullable=False, default="env")
    generation = Column(Integer, nullable=False, default=0)
    last_refreshed_at = Column(DateTime(timezone=True))
    last_validated_at = Column(DateTime(timezone=True))
    data_plan_status = Column(String(64))
    data_valid_until = Column(DateTime(timezone=True))
    last_lease_issued_at = Column(DateTime(timezone=True))


class DhanInstrumentRegistry(Base, BaseModelMixin):
    __tablename__ = "dhan_instrument_registry"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_dhan_instrument_registry_symbol"),
        UniqueConstraint("security_id", name="uq_dhan_instrument_registry_security_id"),
        Index("ix_dhan_instrument_registry_expiry", "expiry"),
    )

    symbol = Column(String(128), nullable=False, index=True)
    security_id = Column(String(64), nullable=False, index=True)
    root_symbol = Column(String(32), nullable=False, default="NIFTY")
    exchange_segment = Column(String(32), nullable=False)
    instrument_type = Column(String(32), nullable=False)
    expiry = Column(String(32), nullable=False)
    strike = Column(Integer, nullable=False)
    option_type = Column(String(8), nullable=False)
    first_seen = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class DhanIncident(Base, BaseModelMixin):
    __tablename__ = "dhan_incidents"

    provider = Column(String(64), nullable=False, unique=True, index=True, default="dhan")
    provider_unhealthy = Column(Boolean, nullable=False, default=False)
    provider_reason = Column(String(128))
    provider_message = Column(Text)
    provider_updated_at = Column(DateTime(timezone=True))
    incident_open = Column(Boolean, nullable=False, default=False)
    incident_class = Column(String(64))
    root_cause = Column(String(128))
    message = Column(Text)
    fingerprint = Column(String(255), index=True)
    opened_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    last_state_change_at = Column(DateTime(timezone=True))
    last_open_alert_at = Column(DateTime(timezone=True))
    last_recovery_alert_at = Column(DateTime(timezone=True))
    affected_consumers = Column(JSON, nullable=False, default=list)
    alert_delivery_error = Column(Text)


class DhanConsumerState(Base, BaseModelMixin):
    __tablename__ = "dhan_consumer_states"
    __table_args__ = (
        UniqueConstraint("consumer", "instance_id", name="uq_dhan_consumer_state_instance"),
        Index("ix_dhan_consumer_states_observed_at", "observed_at"),
    )

    consumer = Column(String(64), nullable=False, index=True)
    instance_id = Column(String(128), nullable=False)
    state = Column(String(32), nullable=False)
    reason = Column(String(128))
    message = Column(Text)
    observed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    generation = Column(Integer)
