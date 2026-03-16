from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from secrets import token_urlsafe
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / "backend" / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Lite Options Terminal"
    app_version: str = "2.3.0"
    app_env: Literal["development", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:5173"
    frontend_origin_regex: str | None = r"^https://(litetrade|lite-options-terminal)(-[a-z0-9-]+)?\.vercel\.app$"
    database_url: str = Field(default=f"sqlite:///{ROOT_DIR / 'data' / 'lite.db'}", alias="LITE_DATABASE_URL")
    jwt_secret: str = Field(default_factory=lambda: token_urlsafe(48))
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    access_cookie_name: str = "lite_access"
    refresh_cookie_name: str = "lite_refresh"
    csrf_cookie_name: str = "lite_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    signal_root: str = str(ROOT_DIR / "signals")
    auto_execute_signals: bool = False
    signal_min_confidence: float = 60.0
    market_poll_seconds: int = 5
    option_chain_refresh_seconds: int = 15
    signal_poll_seconds: int = 15
    quote_refresh_seconds: int = 5
    market_feed_flush_ms: int = 150
    market_feed_reconnect_seconds: int = 3
    dhan_client_id: str | None = Field(default=None, alias="DHAN_CLIENT_ID")
    dhan_access_token: str | None = Field(default=None, alias="DHAN_ACCESS_TOKEN")
    dhan_pin: str | None = Field(default=None, alias="DHAN_PIN")
    dhan_totp_secret: str | None = Field(default=None, alias="DHAN_TOTP_SECRET")
    dhan_http_timeout_seconds: float = Field(default=20.0, alias="DHAN_HTTP_TIMEOUT_SECONDS")
    dhan_profile_check_seconds: int = Field(default=900, alias="DHAN_PROFILE_CHECK_SECONDS")
    dhan_token_renewal_lead_seconds: int = Field(default=3600, alias="DHAN_TOKEN_RENEWAL_LEAD_SECONDS")
    dhan_realtime_stale_seconds: int = Field(default=20, alias="DHAN_REALTIME_STALE_SECONDS")
    dhan_rest_stale_seconds: int = Field(default=45, alias="DHAN_REST_STALE_SECONDS")
    dhan_incident_alert_cooldown_seconds: int = Field(default=28800, alias="DHAN_INCIDENT_ALERT_COOLDOWN_SECONDS")
    dhan_p0_slack_webhook_url: str | None = Field(default=None, alias="DHAN_P0_SLACK_WEBHOOK_URL")
    allow_public_signup: bool = Field(default=True, alias="ALLOW_PUBLIC_SIGNUP")
    bootstrap_admin_email: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_PASSWORD")
    bootstrap_admin_name: str = Field(default="Lite Admin", alias="BOOTSTRAP_ADMIN_NAME")
    bootstrap_agent_key: str | None = Field(default=None, alias="BOOTSTRAP_AGENT_KEY")
    bootstrap_agent_name: str = Field(default="default-agent", alias="BOOTSTRAP_AGENT_NAME")
    agent_key_default_days: int = Field(default=30, alias="AGENT_KEY_DEFAULT_DAYS")
    agent_key_touch_interval_seconds: int = Field(default=300, alias="AGENT_KEY_TOUCH_INTERVAL_SECONDS")
    nifty_lot_size: int = Field(default=65, alias="NIFTY_LOT_SIZE")
    default_frontend_slug: str = "litetrade"
    default_backend_slug: str = "litetrade-api"

    @property
    def signal_root_path(self) -> Path:
        return Path(self.signal_root).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
