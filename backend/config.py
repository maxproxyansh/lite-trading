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
    app_env: Literal["development", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:5173"
    frontend_origin_regex: str | None = None
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
    signal_poll_seconds: int = 15
    quote_refresh_seconds: int = 5
    dhan_client_id: str | None = Field(default=None, alias="DHAN_CLIENT_ID")
    dhan_access_token: str | None = Field(default=None, alias="DHAN_ACCESS_TOKEN")
    bootstrap_admin_email: str = "admin@lite.trade"
    bootstrap_admin_password: str = Field(default_factory=lambda: token_urlsafe(18))
    bootstrap_agent_key: str = Field(default_factory=lambda: f"lite_{token_urlsafe(24)}")
    bootstrap_agent_name: str = "default-agent"
    default_frontend_slug: str = "lite-options-terminal"
    default_backend_slug: str = "lite-options-api"

    @property
    def signal_root_path(self) -> Path:
        return Path(self.signal_root).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
