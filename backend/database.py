from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings


settings = get_settings()
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args: dict[str, object] = {}
if database_url.startswith("sqlite:///"):
    sqlite_path = Path(database_url.replace("sqlite:///", "", 1))
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    connect_args["check_same_thread"] = False

engine = create_engine(database_url, connect_args=connect_args, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from models import BaseModelMixin  # noqa: F401
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)


def _run_migrations(eng) -> None:
    import logging

    logger = logging.getLogger("lite.migrations")
    inspector = inspect(eng)
    if "portfolios" not in inspector.get_table_names():
        return
    columns = [c["name"] for c in inspector.get_columns("portfolios")]
    if "user_id" not in columns:
        with eng.begin() as conn:
            conn.execute(text("ALTER TABLE portfolios ADD COLUMN user_id VARCHAR(64) REFERENCES users(id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_portfolios_user_id ON portfolios (user_id)"))
            logger.info("Migration: added user_id column to portfolios")
    if "kind" not in columns:
        with eng.begin() as conn:
            conn.execute(text("ALTER TABLE portfolios ADD COLUMN kind VARCHAR(16)"))
            conn.execute(text("UPDATE portfolios SET kind = 'agent' WHERE lower(name) LIKE '%agent%' OR lower(id) LIKE 'agent%'"))
            conn.execute(text("UPDATE portfolios SET kind = 'manual' WHERE kind IS NULL"))
            logger.info("Migration: added portfolios.kind column")

    if "agent_api_keys" in inspector.get_table_names():
        agent_columns = [c["name"] for c in inspector.get_columns("agent_api_keys")]
        with eng.begin() as conn:
            if "user_id" not in agent_columns:
                conn.execute(text("ALTER TABLE agent_api_keys ADD COLUMN user_id VARCHAR(64)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_api_keys_user_id ON agent_api_keys (user_id)"))
                logger.info("Migration: added agent_api_keys.user_id column")
            if "portfolio_id" not in agent_columns:
                conn.execute(text("ALTER TABLE agent_api_keys ADD COLUMN portfolio_id VARCHAR(64)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_api_keys_portfolio_id ON agent_api_keys (portfolio_id)"))
                logger.info("Migration: added agent_api_keys.portfolio_id column")
            if "expires_at" not in agent_columns:
                conn.execute(text("ALTER TABLE agent_api_keys ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_api_keys_expires_at ON agent_api_keys (expires_at)"))
                logger.info("Migration: added agent_api_keys.expires_at column")
            if "revoked_at" not in agent_columns:
                conn.execute(text("ALTER TABLE agent_api_keys ADD COLUMN revoked_at TIMESTAMP WITH TIME ZONE"))
                logger.info("Migration: added agent_api_keys.revoked_at column")

    if "service_credentials" in inspector.get_table_names():
        service_columns = [c["name"] for c in inspector.get_columns("service_credentials")]
        with eng.begin() as conn:
            if "generation" not in service_columns:
                conn.execute(text("ALTER TABLE service_credentials ADD COLUMN generation INTEGER NOT NULL DEFAULT 0"))
                logger.info("Migration: added service_credentials.generation column")
            if "data_plan_status" not in service_columns:
                conn.execute(text("ALTER TABLE service_credentials ADD COLUMN data_plan_status VARCHAR(64)"))
                logger.info("Migration: added service_credentials.data_plan_status column")
            if "data_valid_until" not in service_columns:
                conn.execute(text("ALTER TABLE service_credentials ADD COLUMN data_valid_until TIMESTAMP WITH TIME ZONE"))
                logger.info("Migration: added service_credentials.data_valid_until column")
            if "last_lease_issued_at" not in service_columns:
                conn.execute(text("ALTER TABLE service_credentials ADD COLUMN last_lease_issued_at TIMESTAMP WITH TIME ZONE"))
                logger.info("Migration: added service_credentials.last_lease_issued_at column")

    if "dhan_instrument_registry" not in inspector.get_table_names():
        import models

        models.DhanInstrumentRegistry.__table__.create(bind=eng, checkfirst=True)
        logger.info("Migration: created dhan_instrument_registry table")

    if "orders" in inspector.get_table_names():
        order_columns = [c["name"] for c in inspector.get_columns("orders")]
        with eng.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_idempotency_key "
                    "ON orders (idempotency_key) WHERE idempotency_key IS NOT NULL"
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_portfolio_status ON orders (portfolio_id, status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_portfolio_created_at ON orders (portfolio_id, created_at)"))
            if "parent_order_id" not in order_columns:
                conn.execute(text("ALTER TABLE orders ADD COLUMN parent_order_id VARCHAR(64)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_parent_order_id ON orders (parent_order_id)"))
            if "link_type" not in order_columns:
                conn.execute(text("ALTER TABLE orders ADD COLUMN link_type VARCHAR(24)"))
            logger.info("Migration: ensured unique order idempotency index")

    if "alerts" in inspector.get_table_names():
        alert_columns = [c["name"] for c in inspector.get_columns("alerts")]
        with eng.begin() as conn:
            if "portfolio_id" not in alert_columns:
                conn.execute(text("ALTER TABLE alerts ADD COLUMN portfolio_id VARCHAR(64)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_alerts_portfolio_id ON alerts (portfolio_id)"))
                logger.info("Migration: added alerts.portfolio_id column")
            if "creator_agent_key_id" not in alert_columns:
                conn.execute(text("ALTER TABLE alerts ADD COLUMN creator_agent_key_id VARCHAR(64)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_alerts_creator_agent_key_id ON alerts (creator_agent_key_id)"))
                logger.info("Migration: added alerts.creator_agent_key_id column")

    # Add market context columns to fills
    if "fills" in inspector.get_table_names():
        fill_columns = [c["name"] for c in inspector.get_columns("fills")]
        with eng.begin() as conn:
            if "spot_at_fill" not in fill_columns:
                conn.execute(text("ALTER TABLE fills ADD COLUMN spot_at_fill NUMERIC(14,2)"))
                logger.info("Migration: added fills.spot_at_fill column")
            if "vix_at_fill" not in fill_columns:
                conn.execute(text("ALTER TABLE fills ADD COLUMN vix_at_fill NUMERIC(8,2)"))
                logger.info("Migration: added fills.vix_at_fill column")

    # Migrate Float columns to Numeric(14,2) for financial precision
    # PostgreSQL supports ALTER COLUMN TYPE; SQLite ignores column types anyway
    dialect = eng.dialect.name
    if dialect == "postgresql":
        float_to_numeric = [
            ("portfolios", ["starting_cash", "cash_balance", "blocked_margin", "blocked_premium", "realized_pnl"]),
            ("orders", ["price", "trigger_price", "average_price", "last_price", "premium_required", "margin_required", "charges"]),
            ("fills", ["price", "charges"]),
            ("positions", ["average_open_price", "last_price", "blocked_margin", "realized_pnl"]),
            ("daily_stats", ["opening_balance", "closing_balance", "realized_pnl", "unrealized_pnl"]),
        ]
        with eng.begin() as conn:
            for table, cols in float_to_numeric:
                if table not in inspector.get_table_names():
                    continue
                for col in cols:
                    try:
                        conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN "{col}" TYPE NUMERIC(14,2)'))
                    except Exception:
                        pass  # Column may already be correct type
            logger.info("Migration: ensured money columns use NUMERIC(14,2)")
