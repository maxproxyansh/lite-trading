from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint

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
