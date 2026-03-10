from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
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

engine = create_engine(database_url, connect_args=connect_args, future=True)
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
    from sqlalchemy import inspect, text

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

    # One-time cleanup: delete bootstrap admin and orphaned data
    with eng.begin() as conn:
        row = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": "admin@lite.trade"}).fetchone()
        if row:
            admin_id = row[0]
            # Delete orphaned data tied to portfolios with no owner
            for tbl in ("fills", "orders", "positions", "daily_stats"):
                conn.execute(text(f"DELETE FROM {tbl} WHERE portfolio_id IN (SELECT id FROM portfolios WHERE user_id IS NULL)"))
            conn.execute(text("DELETE FROM portfolios WHERE user_id IS NULL"))
            conn.execute(text("DELETE FROM refresh_tokens WHERE user_id = :uid"), {"uid": admin_id})
            conn.execute(text("DELETE FROM audit_logs WHERE actor_id = :uid"), {"uid": admin_id})
            conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": admin_id})
            conn.execute(text("DELETE FROM agent_api_keys WHERE name = :name"), {"name": "default-agent"})
            logger.info("Migration: removed bootstrap admin user and orphaned data")
