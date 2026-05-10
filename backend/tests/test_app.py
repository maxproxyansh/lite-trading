from __future__ import annotations

import asyncio
import base64
import importlib
import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Request, Response
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


_configured_db_url = os.environ.get("LITE_DATABASE_URL", "")
if _configured_db_url.startswith("sqlite:///"):
    TEST_ROOT = Path(_configured_db_url.removeprefix("sqlite:///")).resolve().parent
else:
    TEST_ROOT = Path(tempfile.gettempdir()) / f"lite-backend-tests-{uuid.uuid4().hex}"
SIGNAL_ROOT = Path(os.environ.get("SIGNAL_ROOT", str(TEST_ROOT / "signals"))).resolve()
SIGNAL_ROOT.mkdir(parents=True, exist_ok=True)
(SIGNAL_ROOT / "logs").mkdir(parents=True, exist_ok=True)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("LITE_DATABASE_URL", f"sqlite:///{TEST_ROOT / 'lite-test.db'}")
os.environ.setdefault("SIGNAL_ROOT", str(SIGNAL_ROOT))
os.environ.setdefault("DHAN_CLIENT_ID", "")
os.environ.setdefault("DHAN_ACCESS_TOKEN", "")
os.environ.setdefault("ALLOW_PUBLIC_SIGNUP", "true")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@lite.trade")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "lite-admin-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_NAME", "Lite Admin")
os.environ.setdefault("BOOTSTRAP_AGENT_KEY", "lite-agent-dev-key")
os.environ.setdefault("BOOTSTRAP_AGENT_NAME", "bootstrap-agent")

from database import Base, SessionLocal, engine  # noqa: E402
import main as main_module  # noqa: E402
from main import _process_market_side_effects, app  # noqa: E402
from models import DhanConsumerState, DhanInstrumentRegistry, ServiceCredential, User, WebAuthnCredential  # noqa: E402
from rate_limit import _rate_buckets, _rate_windows, rate_limit  # noqa: E402
from routers.websocket import broadcast_message  # noqa: E402
from services.alert_service import sync_alerts  # noqa: E402
from services.auth_service import ensure_bootstrap_state  # noqa: E402
import dependencies as dependencies_module  # noqa: E402
import services.dhan_credential_service as dhan_credentials_module  # noqa: E402
from services.dhan_credential_service import DhanApiError, DhanCredentialSnapshot, dhan_credential_service  # noqa: E402
from services.dhan_incident_service import DhanIncidentService, dhan_incident_service  # noqa: E402
import services.dhan_incident_service as dhan_incident_service_module  # noqa: E402
import services.market_data as market_data_module  # noqa: E402
from services.market_data import market_data_service  # noqa: E402
from services.signal_adapter import signal_adapter  # noqa: E402
from services.trading_service import process_open_orders_sync  # noqa: E402
from services.webhook_service import process_webhook_deliveries_once, webhook_signature  # noqa: E402
import market_hours  # noqa: E402


meta_router_module = importlib.import_module("routers.meta")
auth_router_module = importlib.import_module("routers.auth")


def _seed_market() -> None:
    market_data_service.snapshot.update(
        {
            "spot_symbol": "NIFTY 50",
            "spot": 22450.0,
            "change": 120.5,
            "change_pct": 0.54,
            "vix": 14.2,
            "pcr": 0.96,
            "pcr_scope": "all_loaded_strikes_for_active_expiry",
            "call_oi_total": 100000.0,
            "put_oi_total": 96000.0,
            "market_status": "OPEN",
            "expiries": ["2026-03-12"],
            "active_expiry": "2026-03-12",
            "degraded": False,
            "degraded_reason": None,
        }
    )
    market_data_service.option_rows = []
    market_data_service.quotes = {
        "NIFTY_2026-03-12_22500_CE": {
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "security_id": "12345",
            "strike": 22500,
            "option_type": "CE",
            "expiry": "2026-03-12",
            "ltp": 112.5,
            "bid": 112.2,
            "ask": 112.8,
            "bid_qty": 500,
            "ask_qty": 450,
            "oi": 100000,
            "volume": 25000,
        }
    }


def _fake_dhan_token(*, issued_at: datetime, expires_at: datetime) -> str:
    def encode(payload: dict[str, object]) -> str:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    header = encode({"typ": "JWT", "alg": "HS256"})
    payload = encode(
        {
            "iss": "dhan",
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
            "dhanClientId": "1103337749",
        }
    )
    return f"{header}.{payload}.signature"


def _reset_test_runtime() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _rate_buckets.clear()
    _rate_windows.clear()
    dhan_credential_service._global_backoff_until = None
    dhan_credential_service._backoff_count = 0
    dhan_credential_service.reset_runtime_state()
    dhan_credential_service.initialize(force_reload=True)
    market_data_service.reset_runtime_state_for_tests()
    db = SessionLocal()
    try:
        ensure_bootstrap_state(db)
    finally:
        db.close()
    _seed_market()


@pytest.fixture(autouse=True)
def _freeze_market_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 12, 10, 0, tzinfo=market_hours.IST),
    )


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _portfolio_map(client: TestClient, headers: dict[str, str]) -> dict[str, dict]:
    response = client.get("/api/v1/portfolios", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    return {item["kind"]: item for item in payload}


def _bootstrap_agent(
    client: TestClient,
    *,
    email: str = "admin@lite.trade",
    password: str = "lite-admin-123",
    agent_name: str = "sdk-agent",
    scopes: list[str] | None = None,
) -> dict:
    response = client.post(
        "/api/v1/agent/bootstrap",
        json={
            "email": email,
            "password": password,
            "agent_name": agent_name,
            "portfolio_kind": "agent",
            "scopes": scopes
            or [
                "orders:read",
                "orders:write",
                "positions:read",
                "positions:write",
                "alerts:read",
                "alerts:write",
                "funds:read",
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def client():
    _reset_test_runtime()
    with TestClient(app) as test_client:
        yield test_client


def test_bootstrap_login_creates_manual_and_agent_portfolios(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    portfolios = _portfolio_map(client, headers)

    assert set(portfolios.keys()) == {"manual", "agent"}
    assert portfolios["manual"]["id"] != portfolios["agent"]["id"]
    assert portfolios["manual"]["available_funds"] == 500000.0
    assert portfolios["agent"]["available_funds"] == 500000.0


def test_public_signup_creates_isolated_manual_and_agent_portfolios(client: TestClient) -> None:
    admin_headers = _login(client, "admin@lite.trade", "lite-admin-123")
    admin_portfolios = _portfolio_map(client, admin_headers)
    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "signup@example.com", "display_name": "Signup User", "password": "signup-pass-1"},
    )
    assert signup.status_code == 200, signup.text

    user_headers = _login(client, "signup@example.com", "signup-pass-1")
    user_portfolios = _portfolio_map(client, user_headers)
    assert set(user_portfolios.keys()) == {"manual", "agent"}
    assert user_portfolios["manual"]["id"] != admin_portfolios["manual"]["id"]

    forbidden = client.get(
        f"/api/v1/funds?portfolio_id={admin_portfolios['manual']['id']}",
        headers=user_headers,
    )
    assert forbidden.status_code == 404


def test_admin_can_create_user_with_isolated_manual_and_agent_portfolios(client: TestClient) -> None:
    admin_headers = _login(client, "admin@lite.trade", "lite-admin-123")
    admin_portfolios = _portfolio_map(client, admin_headers)

    create_user = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "email": "trader@example.com",
            "display_name": "Trader One",
            "password": "trader-pass-1",
            "role": "trader",
        },
    )
    assert create_user.status_code == 200, create_user.text

    trader_headers = _login(client, "trader@example.com", "trader-pass-1")
    trader_portfolios = _portfolio_map(client, trader_headers)

    assert set(trader_portfolios.keys()) == {"manual", "agent"}
    assert trader_portfolios["manual"]["id"] != admin_portfolios["manual"]["id"]
    forbidden = client.get(
        f"/api/v1/funds?portfolio_id={admin_portfolios['manual']['id']}",
        headers=trader_headers,
    )
    assert forbidden.status_code == 404


def test_root_meta_docs_and_openapi_are_agent_discoverable(client: TestClient) -> None:
    root = client.get("/")
    assert root.status_code == 200, root.text
    root_payload = root.json()
    assert root_payload["api_prefix"] == "/api/v1"
    assert root_payload["meta_url"].endswith("/api/v1/meta")
    assert root_payload["docs_url"].endswith("/api/v1/docs")
    assert root_payload["openapi_url"].endswith("/api/v1/openapi.json")

    docs = client.get("/api/v1/docs")
    assert docs.status_code == 200, docs.text
    assert "Swagger UI" in docs.text

    openapi = client.get("/api/v1/openapi.json")
    assert openapi.status_code == 200, openapi.text
    assert "/api/v1/meta" in openapi.json()["paths"]

    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200, meta.text
    payload = meta.json()
    assert payload["docs_url"].endswith("/api/v1/docs")
    assert payload["openapi_url"].endswith("/api/v1/openapi.json")
    assert payload["redoc_url"].endswith("/api/v1/redoc")
    assert payload["meta_url"].endswith("/api/v1/meta")
    assert payload["websocket"]["url"].endswith("/api/v1/ws")
    assert payload["auth"]["human"]["access_token_expires_in_seconds"] == 900
    assert payload["auth"]["agent"]["header"] == "X-API-Key"
    assert payload["auth"]["agent"]["default_key_expires_in_days"] == 30
    assert payload["market_data"]["pcr_scope"] == "all_loaded_strikes_for_active_expiry"
    event_types = {event["type"] for event in payload["websocket"]["events"]}
    assert {"market.snapshot", "option.chain", "option.quotes", "alert.triggered", "portfolio.refresh", "signal.updated"} <= event_types


def test_root_version_and_meta_expose_commit_sha(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    commit_sha = "8841172abcdef1234567890abcdef1234567890"
    monkeypatch.setattr(main_module.settings, "app_commit_sha", commit_sha)
    monkeypatch.setattr(meta_router_module.settings, "app_commit_sha", commit_sha)

    root = client.get("/")
    assert root.status_code == 200, root.text
    assert root.json()["version"] == "2.3.0"
    assert root.json()["commit_sha"] == commit_sha

    version = client.get("/version")
    assert version.status_code == 200, version.text
    assert version.json()["version"] == "2.3.0"
    assert version.json()["commit_sha"] == commit_sha

    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200, meta.text
    assert meta.json()["commit_sha"] == commit_sha


def test_meta_uses_forwarded_host_headers_for_public_urls(client: TestClient) -> None:
    response = client.get(
        "/api/v1/meta",
        headers={
            "Host": "lite-options-api-production.up.railway.app",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "litetrade.vercel.app",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["base_url"] == "https://litetrade.vercel.app"
    assert payload["docs_url"] == "https://litetrade.vercel.app/api/v1/docs"
    assert payload["openapi_url"] == "https://litetrade.vercel.app/api/v1/openapi.json"
    assert payload["websocket"]["url"] == "wss://litetrade.vercel.app/api/v1/ws"


def test_agent_keys_are_portfolio_scoped_and_agent_orders_are_idempotent(client: TestClient) -> None:
    admin_headers = _login(client, "admin@lite.trade", "lite-admin-123")
    portfolios = _portfolio_map(client, admin_headers)
    agent_portfolio_id = portfolios["agent"]["id"]
    manual_portfolio_id = portfolios["manual"]["id"]

    key_response = client.post(
        "/api/v1/auth/api-keys",
        headers=admin_headers,
        json={
            "name": "desk-agent",
            "portfolio_id": agent_portfolio_id,
            "scopes": ["orders:read", "orders:write", "positions:read", "positions:write", "funds:read"],
        },
    )
    assert key_response.status_code == 200, key_response.text
    secret = key_response.json()["secret"]
    assert secret.startswith("lite_")

    missing_idempotency = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": secret},
        json={
            "portfolio_id": agent_portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
        },
    )
    assert missing_idempotency.status_code == 400

    payload = {
        "portfolio_id": agent_portfolio_id,
        "symbol": "NIFTY_2026-03-12_22500_CE",
        "expiry": "2026-03-12",
        "strike": 22500,
        "option_type": "CE",
        "side": "BUY",
        "order_type": "MARKET",
        "product": "NRML",
        "validity": "DAY",
        "lots": 1,
        "idempotency_key": "agent-order-001",
    }
    first = client.post("/api/v1/agent/orders", headers={"X-API-Key": secret}, json=payload)
    second = client.post("/api/v1/agent/orders", headers={"X-API-Key": secret}, json=payload)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]

    agent_orders = client.get("/api/v1/agent/orders", headers={"X-API-Key": secret})
    assert agent_orders.status_code == 200
    assert agent_orders.json()["total"] == 1
    assert len(agent_orders.json()["items"]) == 1

    agent_positions = client.get("/api/v1/agent/positions", headers={"X-API-Key": secret})
    assert agent_positions.status_code == 200
    assert len(agent_positions.json()) == 1
    assert agent_positions.json()[0]["portfolio_id"] == agent_portfolio_id

    wrong_portfolio = dict(payload)
    wrong_portfolio["portfolio_id"] = manual_portfolio_id
    wrong_portfolio["idempotency_key"] = "agent-order-002"
    wrong_response = client.post("/api/v1/agent/orders", headers={"X-API-Key": secret}, json=wrong_portfolio)
    assert wrong_response.status_code == 403

    funds_wrong = client.get(f"/api/v1/agent/funds/{manual_portfolio_id}", headers={"X-API-Key": secret})
    assert funds_wrong.status_code == 403

    close_order = client.post(
        f"/api/v1/agent/positions/{agent_positions.json()[0]['id']}/close",
        headers={"X-API-Key": secret},
    )
    assert close_order.status_code == 200, close_order.text
    assert close_order.json()["side"] == "SELL"


def test_agent_bootstrap_includes_discovery_links_and_key_expiry(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(client, agent_name="discovery-agent")

    assert bootstrap["agent"]["expires_at"] is not None
    assert bootstrap["links"]["meta"] == "/api/v1/meta"
    assert bootstrap["links"]["docs"] == "/api/v1/docs"
    assert bootstrap["links"]["openapi"] == "/api/v1/openapi.json"
    assert bootstrap["links"]["redoc"] == "/api/v1/redoc"
    assert bootstrap["links"]["websocket"] == "/api/v1/ws"
    assert bootstrap["links"]["market_snapshot"] == "/api/v1/market/snapshot"
    assert bootstrap["links"]["market_chain"] == "/api/v1/market/chain"


def test_agent_bootstrap_rotates_same_name_key_and_exposes_profile(client: TestClient) -> None:
    first = _bootstrap_agent(client, agent_name="rotation-agent")
    second = _bootstrap_agent(client, agent_name="rotation-agent")

    assert first["api_key"] != second["api_key"]
    assert first["portfolio"]["kind"] == "agent"
    assert second["agent"]["name"] == "rotation-agent"

    stale = client.get("/api/v1/agent/me", headers={"X-API-Key": first["api_key"]})
    assert stale.status_code == 401

    profile = client.get("/api/v1/agent/me", headers={"X-API-Key": second["api_key"]})
    assert profile.status_code == 200, profile.text
    assert profile.json()["portfolio"]["id"] == second["portfolio"]["id"]
    assert profile.json()["links"]["dhan_orders"] == "/api/v1/agent/dhan/orders"


def test_agent_dhan_order_cancel_and_square_off_all(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(client, agent_name="dhan-agent")
    api_key = bootstrap["api_key"]

    pending = client.post(
        "/api/v1/agent/dhan/orders",
        headers={"X-API-Key": api_key},
        json={
            "transaction_type": "BUY",
            "trading_symbol": "NIFTY_2026-03-12_22500_CE",
            "quantity": 65,
            "order_type": "LIMIT",
            "product_type": "NRML",
            "price": 100.0,
            "correlationId": "dhan-pending-001",
        },
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["orderStatus"] == "OPEN"

    cancelled = client.delete(
        f"/api/v1/agent/dhan/orders/{pending.json()['orderId']}",
        headers={"X-API-Key": api_key},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["orderStatus"] == "CANCELLED"

    filled = client.post(
        "/api/v1/agent/dhan/orders",
        headers={"X-API-Key": api_key},
        json={
            "transaction_type": "BUY",
            "trading_symbol": "NIFTY_2026-03-12_22500_CE",
            "quantity": 65,
            "order_type": "MARKET",
            "product_type": "NRML",
            "correlationId": "dhan-filled-001",
        },
    )
    assert filled.status_code == 200, filled.text
    assert filled.json()["orderStatus"] == "FILLED"

    dhan_positions = client.get("/api/v1/agent/dhan/positions", headers={"X-API-Key": api_key})
    assert dhan_positions.status_code == 200, dhan_positions.text
    assert len(dhan_positions.json()) == 1

    square_off = client.post("/api/v1/agent/positions/square-off", headers={"X-API-Key": api_key})
    assert square_off.status_code == 200, square_off.text
    assert len(square_off.json()) == 1
    assert square_off.json()[0]["side"] == "SELL"

    after = client.get("/api/v1/agent/positions", headers={"X-API-Key": api_key})
    assert after.status_code == 200
    assert after.json() == []

    funds = client.get("/api/v1/agent/dhan/fundlimit", headers={"X-API-Key": api_key})
    assert funds.status_code == 200
    assert funds.json()["accountId"] == bootstrap["portfolio"]["id"]


def test_agent_api_key_can_access_market_routes(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(client, agent_name="market-agent")
    api_key = bootstrap["api_key"]

    snapshot = client.get("/api/v1/market/snapshot", headers={"X-API-Key": api_key})
    assert snapshot.status_code == 200, snapshot.text
    assert snapshot.json()["spot_symbol"] == "NIFTY 50"
    assert snapshot.json()["pcr_scope"] == "all_loaded_strikes_for_active_expiry"
    assert snapshot.json()["call_oi_total"] == 100000.0
    assert snapshot.json()["put_oi_total"] == 96000.0

    expiries = client.get("/api/v1/market/expiries", headers={"X-API-Key": api_key})
    assert expiries.status_code == 200, expiries.text
    assert "expiries" in expiries.json()

    chain = client.get("/api/v1/market/chain", headers={"X-API-Key": api_key})
    assert chain.status_code == 200, chain.text
    assert chain.json()["snapshot"]["active_expiry"] == "2026-03-12"
    assert chain.json()["snapshot"]["pcr_scope"] == "all_loaded_strikes_for_active_expiry"

    candles = client.get("/api/v1/market/candles?timeframe=15m", headers={"X-API-Key": api_key})
    assert candles.status_code == 200, candles.text
    assert candles.json()["timeframe"] == "15m"

    depth = client.get("/api/v1/market/depth/NIFTY_2026-03-12_22500_CE", headers={"X-API-Key": api_key})
    assert depth.status_code == 200, depth.text
    assert depth.json()["symbol"] == "NIFTY_2026-03-12_22500_CE"


def test_market_chain_failed_expiry_switch_keeps_cached_chain(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _bootstrap_agent(client, agent_name="expiry-agent")
    api_key = bootstrap["api_key"]
    original_rows = market_data_service.option_rows
    original_snapshot = dict(market_data_service.snapshot)
    original_expiries = list(market_data_service.expiries)
    original_active_expiry = market_data_service.active_expiry

    call = dict(market_data_service.quotes["NIFTY_2026-03-12_22500_CE"])
    put = {
        **call,
        "symbol": "NIFTY_2026-03-12_22500_PE",
        "option_type": "PE",
        "ltp": 98.4,
        "bid": 98.1,
        "ask": 98.7,
    }

    market_data_service.option_rows = [{"strike": 22500, "is_atm": True, "call": call, "put": put}]
    market_data_service.snapshot.update({"active_expiry": "2026-03-12", "expiries": ["2026-03-12", "2026-03-19"]})
    market_data_service.expiries = ["2026-03-12", "2026-03-19"]
    market_data_service.active_expiry = "2026-03-12"

    async def fake_activate_expiry(expiry: str) -> bool:
        assert expiry == "2026-03-19"
        return False

    monkeypatch.setattr(market_data_service, "activate_expiry", fake_activate_expiry)
    try:
        response = client.get("/api/v1/market/chain?expiry=2026-03-19", headers={"X-API-Key": api_key})
    finally:
        market_data_service.option_rows = original_rows
        market_data_service.snapshot.clear()
        market_data_service.snapshot.update(original_snapshot)
        market_data_service.expiries = original_expiries
        market_data_service.active_expiry = original_active_expiry

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["snapshot"]["active_expiry"] == "2026-03-12"
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["call"]["symbol"] == "NIFTY_2026-03-12_22500_CE"


def test_agent_alerts_are_portfolio_scoped(client: TestClient) -> None:
    admin_headers = _login(client, "admin@lite.trade", "lite-admin-123")
    portfolios = _portfolio_map(client, admin_headers)

    agent_bootstrap = _bootstrap_agent(client, agent_name="alerts-agent")
    agent_key = agent_bootstrap["api_key"]

    manual_key_response = client.post(
        "/api/v1/auth/api-keys",
        headers=admin_headers,
        json={
            "name": "manual-alert-agent",
            "portfolio_id": portfolios["manual"]["id"],
            "scopes": ["alerts:read", "alerts:write", "funds:read"],
        },
    )
    assert manual_key_response.status_code == 200, manual_key_response.text
    manual_key = manual_key_response.json()["secret"]

    agent_alert = client.post(
        "/api/v1/agent/alerts",
        headers={"X-API-Key": agent_key},
        json={"symbol": "NIFTY 50", "target_price": 22500},
    )
    assert agent_alert.status_code == 201, agent_alert.text
    assert agent_alert.json()["portfolio_id"] == agent_bootstrap["portfolio"]["id"]

    manual_alert = client.post(
        "/api/v1/agent/alerts",
        headers={"X-API-Key": manual_key},
        json={"symbol": "NIFTY 50", "target_price": 22300},
    )
    assert manual_alert.status_code == 201, manual_alert.text
    assert manual_alert.json()["portfolio_id"] == portfolios["manual"]["id"]

    list_agent = client.get("/api/v1/agent/alerts", headers={"X-API-Key": agent_key})
    assert list_agent.status_code == 200, list_agent.text
    assert len(list_agent.json()) == 1
    assert list_agent.json()[0]["id"] == agent_alert.json()["id"]

    list_manual = client.get("/api/v1/agent/alerts", headers={"X-API-Key": manual_key})
    assert list_manual.status_code == 200, list_manual.text
    assert len(list_manual.json()) == 1
    assert list_manual.json()[0]["id"] == manual_alert.json()["id"]

    delete_wrong = client.delete(
        f"/api/v1/agent/alerts/{manual_alert.json()['id']}",
        headers={"X-API-Key": agent_key},
    )
    assert delete_wrong.status_code == 404

    delete_right = client.delete(
        f"/api/v1/agent/alerts/{agent_alert.json()['id']}",
        headers={"X-API-Key": agent_key},
    )
    assert delete_right.status_code == 204


def test_agent_can_modify_open_order_and_partially_close_position(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(client, agent_name="modify-agent")
    api_key = bootstrap["api_key"]
    portfolio_id = bootstrap["portfolio"]["id"]

    open_order = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "LIMIT",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "price": 100.0,
            "idempotency_key": "modifiable-open-order",
        },
    )
    assert open_order.status_code == 200, open_order.text
    assert open_order.json()["status"] == "OPEN"

    modified = client.patch(
        f"/api/v1/agent/orders/{open_order.json()['id']}",
        headers={"X-API-Key": api_key},
        json={"price": 111.0, "quantity": 130},
    )
    assert modified.status_code == 200, modified.text
    assert modified.json()["status"] == "OPEN"
    assert modified.json()["price"] == 111.0
    assert modified.json()["quantity"] == 130
    assert modified.json()["lots"] == 2

    filled = client.patch(
        f"/api/v1/agent/orders/{open_order.json()['id']}",
        headers={"X-API-Key": api_key},
        json={"price": 113.0},
    )
    assert filled.status_code == 200, filled.text
    assert filled.json()["status"] == "FILLED"
    assert filled.json()["quantity"] == 130

    top_up = client.post(
        "/api/v1/agent/dhan/orders",
        headers={"X-API-Key": api_key},
        json={
            "transaction_type": "BUY",
            "trading_symbol": "NIFTY_2026-03-12_22500_CE",
            "quantity": 65,
            "order_type": "MARKET",
            "product_type": "NRML",
            "correlationId": "partial-close-top-up",
        },
    )
    assert top_up.status_code == 200, top_up.text

    positions = client.get("/api/v1/agent/positions", headers={"X-API-Key": api_key})
    assert positions.status_code == 200, positions.text
    assert len(positions.json()) == 1
    position_id = positions.json()[0]["id"]
    assert positions.json()[0]["net_quantity"] == 195

    partial_close = client.post(
        f"/api/v1/agent/positions/{position_id}/close?quantity=65",
        headers={"X-API-Key": api_key},
    )
    assert partial_close.status_code == 200, partial_close.text
    assert partial_close.json()["side"] == "SELL"
    assert partial_close.json()["quantity"] == 65

    after_partial = client.get("/api/v1/agent/positions", headers={"X-API-Key": api_key})
    assert after_partial.status_code == 200, after_partial.text
    assert after_partial.json()[0]["net_quantity"] == 130

    final_close = client.post(
        f"/api/v1/agent/positions/{position_id}/close",
        headers={"X-API-Key": api_key},
    )
    assert final_close.status_code == 200, final_close.text
    assert final_close.json()["quantity"] == 130

    after_full_close = client.get("/api/v1/agent/positions", headers={"X-API-Key": api_key})
    assert after_full_close.status_code == 200, after_full_close.text
    assert after_full_close.json() == []


def test_agent_bracket_orders_activate_children_and_cancel_oco_sibling(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(client, agent_name="bracket-agent")
    api_key = bootstrap["api_key"]
    portfolio_id = bootstrap["portfolio"]["id"]

    cancelled_bracket = client.post(
        "/api/v1/agent/orders/bracket",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "lots": 1,
            "entry_order_type": "LIMIT",
            "entry_price": 100.0,
            "stop_loss_price": 94.0,
            "stop_loss_trigger_price": 95.0,
            "target_price": 120.0,
            "idempotency_key": "bracket-cancel-1",
        },
    )
    assert cancelled_bracket.status_code == 200, cancelled_bracket.text
    assert cancelled_bracket.json()["parent"]["status"] == "OPEN"
    assert cancelled_bracket.json()["stop_loss"]["status"] == "PARKED"
    assert cancelled_bracket.json()["target"]["status"] == "PARKED"

    cancel_parent = client.post(
        f"/api/v1/agent/orders/{cancelled_bracket.json()['parent']['id']}/cancel",
        headers={"X-API-Key": api_key},
    )
    assert cancel_parent.status_code == 200, cancel_parent.text

    cancelled_linked = client.get(
        f"/api/v1/agent/orders/{cancelled_bracket.json()['parent']['id']}/linked",
        headers={"X-API-Key": api_key},
    )
    assert cancelled_linked.status_code == 200, cancelled_linked.text
    cancelled_statuses = {item["link_type"]: item["status"] for item in cancelled_linked.json()}
    assert cancelled_statuses["ENTRY"] == "CANCELLED"
    assert cancelled_statuses["STOP_LOSS"] == "CANCELLED"
    assert cancelled_statuses["TARGET"] == "CANCELLED"

    live_bracket = client.post(
        "/api/v1/agent/orders/bracket",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "lots": 1,
            "entry_order_type": "LIMIT",
            "entry_price": 100.0,
            "stop_loss_price": 94.0,
            "stop_loss_trigger_price": 95.0,
            "target_price": 120.0,
            "idempotency_key": "bracket-live-1",
        },
    )
    assert live_bracket.status_code == 200, live_bracket.text

    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ask"] = 99.0
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ltp"] = 99.0
    db = SessionLocal()
    try:
        changed = process_open_orders_sync(db, {"NIFTY_2026-03-12_22500_CE"})
        assert changed == {portfolio_id}
    finally:
        db.close()

    activated_linked = client.get(
        f"/api/v1/agent/orders/{live_bracket.json()['parent']['id']}/linked",
        headers={"X-API-Key": api_key},
    )
    assert activated_linked.status_code == 200, activated_linked.text
    activated_statuses = {item["link_type"]: item["status"] for item in activated_linked.json()}
    assert activated_statuses["ENTRY"] == "FILLED"
    assert activated_statuses["STOP_LOSS"] == "TRIGGER_PENDING"
    assert activated_statuses["TARGET"] == "OPEN"

    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["bid"] = 121.0
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ask"] = 121.2
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ltp"] = 121.0
    db = SessionLocal()
    try:
        changed = process_open_orders_sync(db, {"NIFTY_2026-03-12_22500_CE"})
        assert changed == {portfolio_id}
    finally:
        db.close()

    final_linked = client.get(
        f"/api/v1/agent/orders/{live_bracket.json()['parent']['id']}/linked",
        headers={"X-API-Key": api_key},
    )
    assert final_linked.status_code == 200, final_linked.text
    final_statuses = {item["link_type"]: item["status"] for item in final_linked.json()}
    assert final_statuses["TARGET"] == "FILLED"
    assert final_statuses["STOP_LOSS"] == "CANCELLED"

    positions = client.get("/api/v1/agent/positions", headers={"X-API-Key": api_key})
    assert positions.status_code == 200, positions.text
    assert positions.json() == []


def test_agent_orders_support_filters_and_pagination(client: TestClient) -> None:
    market_data_service.quotes["BANKNIFTY_2026-03-12_51000_CE"] = {
        "symbol": "BANKNIFTY_2026-03-12_51000_CE",
        "security_id": "98765",
        "strike": 51000,
        "option_type": "CE",
        "expiry": "2026-03-12",
        "ltp": 210.0,
        "bid": 209.5,
        "ask": 210.5,
        "bid_qty": 100,
        "ask_qty": 100,
        "oi": 50000,
        "volume": 12000,
    }

    bootstrap = _bootstrap_agent(client, agent_name="filter-agent")
    api_key = bootstrap["api_key"]
    portfolio_id = bootstrap["portfolio"]["id"]

    filled = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "idempotency_key": "orders-filter-filled",
        },
    )
    assert filled.status_code == 200, filled.text

    open_nifty = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "LIMIT",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "price": 100.0,
            "idempotency_key": "orders-filter-open-nifty",
        },
    )
    assert open_nifty.status_code == 200, open_nifty.text

    open_banknifty = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "BANKNIFTY_2026-03-12_51000_CE",
            "expiry": "2026-03-12",
            "strike": 51000,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "LIMIT",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "price": 200.0,
            "idempotency_key": "orders-filter-open-banknifty",
        },
    )
    assert open_banknifty.status_code == 200, open_banknifty.text

    db = SessionLocal()
    try:
        from models import Order

        timestamps = {
            filled.json()["id"]: datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            open_nifty.json()["id"]: datetime(2026, 3, 4, 10, 0, tzinfo=timezone.utc),
            open_banknifty.json()["id"]: datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc),
        }
        for order_id, created_at in timestamps.items():
            order = db.query(Order).filter(Order.id == order_id).first()
            assert order is not None
            order.created_at = created_at
            order.requested_at = created_at
        db.commit()
    finally:
        db.close()

    filtered = client.get(
        "/api/v1/agent/orders?status=OPEN&symbol=BANKNIFTY&from=2026-03-05&to=2026-03-10&offset=0&limit=5&sort=asc",
        headers={"X-API-Key": api_key},
    )
    assert filtered.status_code == 200, filtered.text
    payload = filtered.json()
    assert payload["total"] == 1
    assert payload["offset"] == 0
    assert payload["limit"] == 5
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == open_banknifty.json()["id"]

    paged = client.get(
        "/api/v1/agent/orders?offset=0&limit=1&sort=asc",
        headers={"X-API-Key": api_key},
    )
    assert paged.status_code == 200, paged.text
    assert paged.json()["total"] == 3
    assert len(paged.json()["items"]) == 1
    assert paged.json()["items"][0]["id"] == filled.json()["id"]


def test_agent_detailed_analytics_returns_trade_breakdowns(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(client, agent_name="analytics-agent")
    api_key = bootstrap["api_key"]
    portfolio_id = bootstrap["portfolio"]["id"]

    first_buy = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "idempotency_key": "analytics-buy-1",
        },
    )
    assert first_buy.status_code == 200, first_buy.text

    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["bid"] = 125.0
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ask"] = 125.2
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ltp"] = 125.0
    first_sell = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "SELL",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "idempotency_key": "analytics-sell-1",
        },
    )
    assert first_sell.status_code == 200, first_sell.text

    second_buy = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "idempotency_key": "analytics-buy-2",
        },
    )
    assert second_buy.status_code == 200, second_buy.text

    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["bid"] = 100.0
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ask"] = 100.2
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ltp"] = 100.0
    second_sell = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "SELL",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "idempotency_key": "analytics-sell-2",
        },
    )
    assert second_sell.status_code == 200, second_sell.text

    today = datetime.now(timezone.utc).date().isoformat()
    detailed = client.get(
        f"/api/v1/agent/analytics/detailed?from={today}&to={today}",
        headers={"X-API-Key": api_key},
    )
    assert detailed.status_code == 200, detailed.text
    payload = detailed.json()
    assert payload["portfolio_id"] == portfolio_id
    assert payload["total_closed_trades"] == 2
    assert len(payload["closed_trades"]) == 2
    assert payload["trade_attribution"][0]["symbol"] == "NIFTY_2026-03-12_22500_CE"
    assert payload["average_hold_seconds"] >= 0
    assert payload["max_consecutive_wins"] >= 1
    assert payload["max_consecutive_losses"] >= 1
    assert sum(bucket["value"] for bucket in payload["win_loss_distribution"]) == 2


def test_agent_detailed_analytics_counts_trades_closed_inside_window(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(client, agent_name="analytics-window-agent")
    api_key = bootstrap["api_key"]
    portfolio_id = bootstrap["portfolio"]["id"]

    buy = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "idempotency_key": "analytics-window-buy",
        },
    )
    assert buy.status_code == 200, buy.text

    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["bid"] = 124.0
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ask"] = 124.2
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ltp"] = 124.0
    sell = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "SELL",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "idempotency_key": "analytics-window-sell",
        },
    )
    assert sell.status_code == 200, sell.text

    db = SessionLocal()
    try:
        from models import Fill

        buy_fill = db.query(Fill).filter(Fill.order_id == buy.json()["id"]).first()
        sell_fill = db.query(Fill).filter(Fill.order_id == sell.json()["id"]).first()
        assert buy_fill is not None
        assert sell_fill is not None
        buy_fill.executed_at = datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc)
        sell_fill.executed_at = datetime(2026, 3, 11, 10, 0, tzinfo=timezone.utc)
        db.commit()
    finally:
        db.close()

    detailed = client.get(
        "/api/v1/agent/analytics/detailed?from=2026-03-11&to=2026-03-11",
        headers={"X-API-Key": api_key},
    )
    assert detailed.status_code == 200, detailed.text
    payload = detailed.json()
    assert payload["total_closed_trades"] == 1
    assert len(payload["closed_trades"]) == 1
    assert payload["closed_trades"][0]["exit_time"].startswith("2026-03-11T10:00:00")


def test_agent_websocket_receives_option_quote_batches(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(client, agent_name="quote-ws-agent")
    api_key = bootstrap["api_key"]

    with client.websocket_connect("/api/v1/ws", headers={"X-API-Key": api_key}) as websocket:
        market_data_service._security_id_to_symbol = {"12345": "NIFTY_2026-03-12_22500_CE"}
        market_data_service._handle_feed_packet(
            {
                "type": "Full Data",
                "security_id": 12345,
                "LTP": "119.25",
                "volume": 28000,
                "OI": 121000,
                "depth": [
                    {
                        "bid_price": "119.20",
                        "ask_price": "119.35",
                        "bid_quantity": 700,
                        "ask_quantity": 650,
                    }
                ],
            }
        )
        asyncio.run(
            broadcast_message(
                "option.quotes",
                market_data_service._build_quote_batch(tuple(market_data_service._dirty_quote_symbols)),
            )
        )
        message = websocket.receive_json()
        assert message["type"] == "option.quotes"
        assert message["payload"]["quotes"][0]["symbol"] == "NIFTY_2026-03-12_22500_CE"
        assert message["payload"]["quotes"][0]["ltp"] == 119.25


def test_rate_limited_endpoints_emit_headers_on_success_and_429(client: TestClient) -> None:
    success = client.post(
        "/api/v1/agent/bootstrap",
        json={
            "email": "admin@lite.trade",
            "password": "lite-admin-123",
            "agent_name": "rate-limit-agent",
            "portfolio_kind": "agent",
        },
    )
    assert success.status_code == 200, success.text
    for header in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
        assert header in success.headers

    _rate_buckets["agent:bootstrap:ip:testclient"] = [time.time()] * 10
    _rate_windows["agent:bootstrap:ip:testclient"] = 60
    limited = client.post(
        "/api/v1/agent/bootstrap",
        json={
            "email": "admin@lite.trade",
            "password": "lite-admin-123",
            "agent_name": "rate-limit-agent-2",
            "portfolio_kind": "agent",
        },
    )
    assert limited.status_code == 429, limited.text
    assert limited.headers["X-RateLimit-Limit"] == "10"
    assert limited.headers["X-RateLimit-Remaining"] == "0"
    assert limited.headers["X-RateLimit-Reset"]


def test_rate_limit_does_not_prune_longer_window_buckets() -> None:
    _rate_buckets.clear()
    _rate_windows.clear()

    now = time.time()
    _rate_buckets["long-window:ip:testclient"] = [now - 120]
    _rate_windows["long-window:ip:testclient"] = 3600

    dependency = rate_limit("short-window", 5, 60)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/rate-test",
            "headers": [],
            "client": ("testclient", 50000),
            "scheme": "http",
            "server": ("testserver", 80),
            "root_path": "",
            "query_string": b"",
            "http_version": "1.1",
        }
    )
    response = Response()

    dependency(request, response)

    assert _rate_buckets["long-window:ip:testclient"] == [now - 120]


def test_dhan_rate_limiter_blocks_when_exhausted() -> None:
    """Token bucket should block when tokens are exhausted."""
    from services.dhan_credential_service import DhanRateLimiter

    limiter = DhanRateLimiter(rate_per_second=10.0, capacity=2)
    assert limiter.acquire(timeout=0.01) is True
    assert limiter.acquire(timeout=0.01) is True
    assert limiter.acquire(timeout=0.01) is False


def test_dhan_rate_limiter_refills_over_time() -> None:
    """Token bucket should refill tokens based on elapsed time."""
    from services.dhan_credential_service import DhanRateLimiter
    import time

    limiter = DhanRateLimiter(rate_per_second=100.0, capacity=1)
    assert limiter.acquire(timeout=0) is True
    assert limiter.acquire(timeout=0) is False
    time.sleep(0.02)
    assert limiter.acquire(timeout=0) is True


def test_dhan_call_activates_global_backoff_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    from services.dhan_credential_service import dhan_credential_service, DhanApiError, DhanCredentialSnapshot

    monkeypatch.setattr(dhan_credential_service, "_global_backoff_until", None)
    monkeypatch.setattr(dhan_credential_service, "_backoff_count", 0)

    def fake_unwrap(op, result):
        raise DhanApiError("DHAN_RATE_LIMITED", "Too many requests")

    monkeypatch.setattr(dhan_credential_service, "_unwrap_sdk_result", fake_unwrap)
    monkeypatch.setattr(dhan_credential_service, "ensure_token_fresh", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        dhan_credential_service,
        "snapshot",
        lambda: DhanCredentialSnapshot(
            configured=True,
            client_id="1103337749",
            access_token="token",
            expires_at=None,
            token_source="totp",
            last_refreshed_at=None,
            last_profile_checked_at=None,
            last_rest_success_at=None,
            data_plan_status="Active",
            data_valid_until=None,
            last_lease_issued_at=None,
            generation=1,
            totp_regeneration_enabled=True,
        ),
    )

    with pytest.raises(DhanApiError, match="Too many requests"):
        dhan_credential_service.call("test_op", lambda c: {})

    assert dhan_credential_service._global_backoff_until is not None
    assert dhan_credential_service._backoff_count == 1

    with pytest.raises(DhanApiError, match="global backoff active"):
        dhan_credential_service.call("test_op2", lambda c: {})


def test_agent_webhooks_register_and_deliver_signed_events(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    bootstrap = _bootstrap_agent(
        client,
        agent_name="webhook-agent",
        scopes=[
            "orders:read",
            "orders:write",
            "positions:read",
            "positions:write",
            "alerts:read",
            "alerts:write",
            "funds:read",
            "webhooks:read",
            "webhooks:write",
        ],
    )
    api_key = bootstrap["api_key"]
    portfolio_id = bootstrap["portfolio"]["id"]

    created = client.post(
        "/api/v1/agent/webhooks",
        headers={"X-API-Key": api_key},
        json={
            "url": "https://agent.example/webhooks",
            "events": ["order.filled", "position.closed"],
        },
    )
    assert created.status_code == 201, created.text
    secret = created.json()["secret"]

    listed = client.get("/api/v1/agent/webhooks", headers={"X-API-Key": api_key})
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    assert "secret" not in listed.json()[0]

    captured: list[tuple[str, bytes, dict[str, str]]] = []

    async def fake_post(self, url, content=None, headers=None):  # noqa: ANN001
        captured.append((url, content or b"", headers or {}))

        class Response:
            status_code = 200

        return Response()

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    order = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": api_key},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "idempotency_key": "webhook-order-filled",
        },
    )
    assert order.status_code == 200, order.text

    delivered = asyncio.run(process_webhook_deliveries_once())
    assert delivered >= 1
    assert captured
    url, body, headers = captured[0]
    assert url == "https://agent.example/webhooks"
    assert headers["X-Webhook-Event"] == "order.filled"
    assert headers["X-Webhook-Signature"] == webhook_signature(body, secret)

    payload = json.loads(body.decode("utf-8"))
    assert payload["event"] == "order.filled"
    assert payload["portfolio_id"] == portfolio_id
    assert payload["data"]["order_id"] == order.json()["id"]

    deleted = client.delete(
        f"/api/v1/agent/webhooks/{created.json()['id']}",
        headers={"X-API-Key": api_key},
    )
    assert deleted.status_code == 204, deleted.text


def test_agent_alerts_create_claimable_events_and_support_ack(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(
        client,
        agent_name="events-agent",
        scopes=[
            "alerts:read",
            "alerts:write",
            "events:read",
            "events:write",
            "funds:read",
        ],
    )
    api_key = bootstrap["api_key"]
    agent_key_id = bootstrap["agent"]["id"]
    symbol = "NIFTY_2026-03-12_22500_CE"

    created = client.post(
        "/api/v1/agent/alerts",
        headers={"X-API-Key": api_key},
        json={"symbol": symbol, "target_price": 115.0},
    )
    assert created.status_code == 201, created.text
    alert_id = created.json()["id"]

    market_data_service.quotes[symbol]["ltp"] = 116.25
    asyncio.run(_process_market_side_effects({symbol}))

    claimed = client.post(
        "/api/v1/agent/events/claim",
        headers={"X-API-Key": api_key},
        json={"limit": 10, "lease_seconds": 30},
    )
    assert claimed.status_code == 200, claimed.text
    payload = claimed.json()
    assert len(payload) == 1
    event = payload[0]
    assert event["type"] == "alert.triggered"
    assert event["agent_key_id"] == agent_key_id
    assert event["source"] == {"type": "alert", "id": alert_id}
    assert event["data"]["alert_id"] == alert_id
    assert event["data"]["symbol"] == symbol
    assert event["acked_at"] is None

    claimed_again = client.post(
        "/api/v1/agent/events/claim",
        headers={"X-API-Key": api_key},
        json={"limit": 10, "lease_seconds": 30},
    )
    assert claimed_again.status_code == 200, claimed_again.text
    assert claimed_again.json() == []

    acked = client.post(
        f"/api/v1/agent/events/{event['id']}/ack",
        headers={"X-API-Key": api_key},
    )
    assert acked.status_code == 200, acked.text
    assert acked.json()["acked_at"] is not None

    claimed_after_ack = client.post(
        "/api/v1/agent/events/claim",
        headers={"X-API-Key": api_key},
        json={"limit": 10, "lease_seconds": 30},
    )
    assert claimed_after_ack.status_code == 200, claimed_after_ack.text
    assert claimed_after_ack.json() == []


def test_agent_websocket_receives_immediate_agent_event_for_triggered_alert(client: TestClient) -> None:
    bootstrap = _bootstrap_agent(
        client,
        agent_name="agent-event-ws",
        scopes=[
            "alerts:read",
            "alerts:write",
            "events:read",
            "events:write",
            "funds:read",
        ],
    )
    api_key = bootstrap["api_key"]
    agent_key_id = bootstrap["agent"]["id"]
    symbol = "NIFTY_2026-03-12_22500_CE"

    created = client.post(
        "/api/v1/agent/alerts",
        headers={"X-API-Key": api_key},
        json={"symbol": symbol, "target_price": 115.0},
    )
    assert created.status_code == 201, created.text
    alert_id = created.json()["id"]

    market_data_service.quotes[symbol]["ltp"] = 116.25

    with client.websocket_connect("/api/v1/ws", headers={"X-API-Key": api_key}) as websocket:
        asyncio.run(_process_market_side_effects({symbol}))
        message = websocket.receive_json()

    assert message["type"] == "agent.event"
    payload = message["payload"]
    assert payload["type"] == "alert.triggered"
    assert payload["agent_key_id"] == agent_key_id
    assert payload["source"] == {"type": "alert", "id": alert_id}
    assert payload["data"]["alert_id"] == alert_id
    assert payload["data"]["last_price"] == 116.25


def test_agent_alert_webhooks_are_targeted_to_creating_agent(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _bootstrap_agent(
        client,
        agent_name="alert-webhook-a",
        scopes=[
            "alerts:read",
            "alerts:write",
            "events:read",
            "events:write",
            "webhooks:read",
            "webhooks:write",
            "funds:read",
        ],
    )
    second = _bootstrap_agent(
        client,
        agent_name="alert-webhook-b",
        scopes=[
            "alerts:read",
            "alerts:write",
            "events:read",
            "events:write",
            "webhooks:read",
            "webhooks:write",
            "funds:read",
        ],
    )

    create_first = client.post(
        "/api/v1/agent/webhooks",
        headers={"X-API-Key": first["api_key"]},
        json={"url": "https://agent-one.example/webhooks", "events": ["alert.triggered"]},
    )
    assert create_first.status_code == 201, create_first.text
    first_secret = create_first.json()["secret"]

    create_second = client.post(
        "/api/v1/agent/webhooks",
        headers={"X-API-Key": second["api_key"]},
        json={"url": "https://agent-two.example/webhooks", "events": ["alert.triggered"]},
    )
    assert create_second.status_code == 201, create_second.text

    captured: list[tuple[str, bytes, dict[str, str]]] = []

    async def fake_post(self, url, content=None, headers=None):  # noqa: ANN001
        captured.append((url, content or b"", headers or {}))

        class Response:
            status_code = 200

        return Response()

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    symbol = "NIFTY_2026-03-12_22500_CE"
    created = client.post(
        "/api/v1/agent/alerts",
        headers={"X-API-Key": first["api_key"]},
        json={"symbol": symbol, "target_price": 115.0},
    )
    assert created.status_code == 201, created.text
    alert_id = created.json()["id"]

    market_data_service.quotes[symbol]["ltp"] = 116.25
    asyncio.run(_process_market_side_effects({symbol}))

    delivered = asyncio.run(process_webhook_deliveries_once())
    assert delivered == 1
    assert len(captured) == 1

    url, body, headers = captured[0]
    assert url == "https://agent-one.example/webhooks"
    assert headers["X-Webhook-Event"] == "alert.triggered"
    assert headers["X-Webhook-Signature"] == webhook_signature(body, first_secret)
    assert headers["X-Lite-Event-Type"] == "alert.triggered"

    payload = json.loads(body.decode("utf-8"))
    assert payload["type"] == "alert.triggered"
    assert payload["agent_key_id"] == first["agent"]["id"]
    assert payload["source"] == {"type": "alert", "id": alert_id}
    assert payload["data"]["alert_id"] == alert_id


def test_unauthenticated_market_access_rejected(client: TestClient) -> None:
    for path in ["/api/v1/market/snapshot", "/api/v1/market/expiries", "/api/v1/market/chain", "/api/v1/market/candles", "/api/v1/market/depth/NIFTY"]:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} should reject unauthenticated requests, got {resp.status_code}"


def test_refresh_and_logout_require_csrf(client: TestClient) -> None:
    login = client.post("/api/v1/auth/login", json={"email": "admin@lite.trade", "password": "lite-admin-123"})
    assert login.status_code == 200, login.text

    refresh = client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 403, refresh.text
    assert refresh.json()["detail"] == "CSRF validation failed"

    csrf_token = client.cookies.get("lite_csrf")
    assert csrf_token

    refreshed = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf_token})
    assert refreshed.status_code == 200, refreshed.text

    logout_without_csrf = client.post("/api/v1/auth/logout")
    assert logout_without_csrf.status_code == 403, logout_without_csrf.text
    assert logout_without_csrf.json()["detail"] == "CSRF validation failed"

    logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": client.cookies.get("lite_csrf") or ""})
    assert logout.status_code == 200, logout.text


def test_human_sell_and_close_releases_margin(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    csrf_token = client.cookies.get("lite_csrf")
    portfolios = _portfolio_map(client, headers)
    manual_portfolio_id = portfolios["manual"]["id"]

    sell_order = client.post(
        "/api/v1/orders",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "portfolio_id": manual_portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "SELL",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
        },
    )
    assert sell_order.status_code == 200, sell_order.text

    positions = client.get(f"/api/v1/positions?portfolio_id={manual_portfolio_id}", headers=headers)
    assert positions.status_code == 200, positions.text
    payload = positions.json()
    assert len(payload) == 1
    assert payload[0]["net_quantity"] < 0

    funds = client.get(f"/api/v1/funds?portfolio_id={manual_portfolio_id}", headers=headers)
    assert funds.status_code == 200, funds.text
    assert funds.json()["blocked_margin"] > 0

    close_order = client.post(
        f"/api/v1/positions/{payload[0]['id']}/close",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert close_order.status_code == 200, close_order.text

    funds_after = client.get(f"/api/v1/funds?portfolio_id={manual_portfolio_id}", headers=headers)
    assert funds_after.status_code == 200, funds_after.text
    assert funds_after.json()["blocked_margin"] == 0.0


def test_human_orders_reject_outside_market_hours(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 12, 9, 5, tzinfo=market_hours.IST),
    )
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    csrf_token = client.cookies.get("lite_csrf")
    portfolio_id = _portfolio_map(client, headers)["manual"]["id"]
    response = client.post(
        "/api/v1/orders",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
        },
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == (
        "Order rejected: NSE F&O regular trading starts at 9:15 AM IST. "
        "Lite does not support pre-open or after-market order entry."
    )


def test_agent_orders_reject_on_trading_holiday(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 26, 10, 0, tzinfo=market_hours.IST),
    )
    bootstrap = _bootstrap_agent(client, agent_name="holiday-agent")
    response = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": bootstrap["api_key"]},
        json={
            "portfolio_id": bootstrap["portfolio"]["id"],
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "MARKET",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "idempotency_key": "holiday-agent-order",
        },
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == (
        "Order rejected: NSE F&O is closed on March 26, 2026 for Shri Ram Navami. "
        "Lite accepts orders only on trading days between 9:15 AM to 3:30 PM IST."
    )


def test_process_open_orders_does_not_fill_when_market_closed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    csrf_token = client.cookies.get("lite_csrf")
    portfolio_id = _portfolio_map(client, headers)["manual"]["id"]

    response = client.post(
        "/api/v1/orders",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "LIMIT",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
            "price": 111.0,
            "idempotency_key": "closed-market-open-order",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "OPEN"

    original_quote = dict(market_data_service.quotes["NIFTY_2026-03-12_22500_CE"])
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"].update({"ltp": 111.2, "bid": 110.9, "ask": 110.5})
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 12, 15, 45, tzinfo=market_hours.IST),
    )
    try:
        with SessionLocal() as db:
            changed = process_open_orders_sync(db, {"NIFTY_2026-03-12_22500_CE"})
    finally:
        market_data_service.quotes["NIFTY_2026-03-12_22500_CE"] = original_quote

    assert changed == set()
    orders = client.get(f"/api/v1/orders?portfolio_id={portfolio_id}", headers=headers)
    assert orders.status_code == 200, orders.text
    assert orders.json()[0]["status"] == "OPEN"


def test_order_request_validation_rejects_missing_limit_price(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    portfolio_id = _portfolio_map(client, headers)["manual"]["id"]
    response = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "LIMIT",
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
        },
    )
    assert response.status_code == 422


def test_alerts_are_user_isolated_and_trigger_against_spot(client: TestClient) -> None:
    admin_headers = _login(client, "admin@lite.trade", "lite-admin-123")
    created = client.post(
        "/api/v1/alerts",
        headers=admin_headers,
        json={"symbol": "NIFTY 50", "target_price": 22500},
    )
    assert created.status_code == 201, created.text
    alert_id = created.json()["id"]
    assert created.json()["direction"] == "ABOVE"
    assert created.json()["status"] == "ACTIVE"

    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "alerts@example.com", "display_name": "Alert User", "password": "alert-pass-1"},
    )
    assert signup.status_code == 200, signup.text
    user_headers = _login(client, "alerts@example.com", "alert-pass-1")
    other_user_alerts = client.get("/api/v1/alerts", headers=user_headers)
    assert other_user_alerts.status_code == 200, other_user_alerts.text
    assert other_user_alerts.json() == []

    market_data_service.snapshot["spot"] = 22510.0
    db = SessionLocal()
    try:
        assert len(sync_alerts(db)) == 1
    finally:
        db.close()

    admin_alerts = client.get("/api/v1/alerts", headers=admin_headers)
    assert admin_alerts.status_code == 200, admin_alerts.text
    payload = admin_alerts.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "TRIGGERED"

    market_data_service.snapshot["spot"] = 22490.0
    updated = client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers=admin_headers,
        json={"target_price": 22450},
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["target_price"] == 22450
    assert updated_payload["direction"] == "BELOW"
    assert updated_payload["status"] == "ACTIVE"
    assert updated_payload["triggered_at"] is None

    deleted = client.delete(f"/api/v1/alerts/{alert_id}", headers=admin_headers)
    assert deleted.status_code == 204, deleted.text
    after_delete = client.get("/api/v1/alerts", headers=admin_headers)
    assert after_delete.status_code == 200, after_delete.text
    assert after_delete.json() == []


def test_alerts_can_trigger_against_option_quotes(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    symbol = "NIFTY_2026-03-12_22500_CE"
    created = client.post(
        "/api/v1/alerts",
        headers=headers,
        json={"symbol": symbol, "target_price": 115.0},
    )
    assert created.status_code == 201, created.text
    created_payload = created.json()
    assert created_payload["symbol"] == symbol
    assert created_payload["direction"] == "ABOVE"
    assert created_payload["status"] == "ACTIVE"
    assert created_payload["last_price"] == 112.5

    market_data_service.quotes[symbol]["ltp"] = 116.25

    with client.websocket_connect("/api/v1/ws", headers=headers) as websocket:
        asyncio.run(_process_market_side_effects({symbol}))
        message = websocket.receive_json()

    assert message["type"] == "alert.triggered"
    assert message["payload"]["id"] == created_payload["id"]
    assert message["payload"]["symbol"] == symbol
    assert message["payload"]["status"] == "TRIGGERED"
    assert message["payload"]["last_price"] == 116.25

    alerts = client.get("/api/v1/alerts", headers=headers)
    assert alerts.status_code == 200, alerts.text
    listed = alerts.json()
    assert len(listed) == 1
    assert listed[0]["id"] == created_payload["id"]
    assert listed[0]["status"] == "TRIGGERED"
    assert listed[0]["last_price"] == 116.25


def test_signal_adapter_keeps_actionable_signal_when_targets_are_advisory(client: TestClient) -> None:
    payload = {
        "timestamp": "2026-03-06T09:20:00+05:30",
        "direction": "bullish",
        "confidence": "high",
        "confidence_score": 82,
        "trade": "BUY NIFTY 22500 CE",
        "strike": 22500,
        "option_type": "CE",
        "expiry": "2026-03-12",
        "entry_range": [108, 112],
        "target": 105,
        "stop_loss": 120,
    }
    (SIGNAL_ROOT / "latest_signal.json").write_text(json.dumps(payload))

    asyncio.run(signal_adapter.ingest_once())
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    response = client.get("/api/v1/signals/latest", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_actionable"] is True
    assert response.json()["target_valid"] is False
    assert response.json()["stop_valid"] is False


def test_websocket_requires_auth_and_streams_events(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.receive_text()
    assert exc.value.code == 4401

    admin_headers = _login(client, "admin@lite.trade", "lite-admin-123")
    with client.websocket_connect("/api/v1/ws", headers={"origin": "http://localhost:5173"}) as websocket:
        asyncio.run(broadcast_message("market.snapshot", {"spot": 22510}))
        message = websocket.receive_json()
        assert message["type"] == "market.snapshot"
        assert message["payload"]["spot"] == 22510

    portfolios = _portfolio_map(client, admin_headers)
    key_response = client.post(
        "/api/v1/auth/api-keys",
        headers=admin_headers,
        json={
            "name": "ws-agent",
            "portfolio_id": portfolios["agent"]["id"],
            "scopes": ["orders:read", "orders:write", "positions:read", "positions:write", "funds:read"],
        },
    )
    assert key_response.status_code == 200, key_response.text
    secret = key_response.json()["secret"]

    with client.websocket_connect("/api/v1/ws", headers={"X-API-Key": secret}) as websocket:
        asyncio.run(broadcast_message("market.snapshot", {"spot": 22525}))
        message = websocket.receive_json()
        assert message["type"] == "market.snapshot"
        assert message["payload"]["spot"] == 22525


def test_websocket_rejects_untrusted_browser_origin(client: TestClient) -> None:
    _login(client, "admin@lite.trade", "lite-admin-123")

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/ws", headers={"origin": "https://evil.example"}) as websocket:
            websocket.receive_text()
    assert exc.value.code == 4403


def test_websocket_pushes_triggered_alerts_immediately(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    created = client.post(
        "/api/v1/alerts",
        headers=headers,
        json={"symbol": "NIFTY 50", "target_price": 22500},
    )
    assert created.status_code == 201, created.text
    alert_id = created.json()["id"]

    market_data_service.snapshot["spot"] = 22510.0

    with client.websocket_connect("/api/v1/ws", headers=headers) as websocket:
        asyncio.run(_process_market_side_effects(set()))
        message = websocket.receive_json()

    assert message["type"] == "alert.triggered"
    assert message["payload"]["id"] == alert_id
    assert message["payload"]["status"] == "TRIGGERED"
    assert message["payload"]["last_price"] == 22510.0


def test_process_open_orders_filters_symbols_and_only_updates_impacted_portfolios(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    csrf_token = client.cookies.get("lite_csrf")
    portfolio_id = _portfolio_map(client, headers)["manual"]["id"]

    response = client.post(
        "/api/v1/orders",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "portfolio_id": portfolio_id,
            "symbol": "NIFTY_2026-03-12_22500_CE",
            "expiry": "2026-03-12",
            "strike": 22500,
            "option_type": "CE",
            "side": "BUY",
            "order_type": "LIMIT",
            "price": 110.0,
            "product": "NRML",
            "validity": "DAY",
            "lots": 1,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "OPEN"

    db = SessionLocal()
    try:
        skipped = process_open_orders_sync(db, {"NIFTY_2026-03-12_22600_CE"})
        assert skipped == set()
    finally:
        db.close()

    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ask"] = 109.0
    market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]["ltp"] = 109.0

    db = SessionLocal()
    try:
        changed = process_open_orders_sync(db, {"NIFTY_2026-03-12_22500_CE"})
        assert changed == {portfolio_id}
    finally:
        db.close()

    orders = client.get(f"/api/v1/orders?portfolio_id={portfolio_id}", headers=headers)
    assert orders.status_code == 200, orders.text
    assert orders.json()[0]["status"] == "FILLED"


def test_market_data_feed_packets_update_live_snapshot_and_quote_batch() -> None:
    _seed_market()
    market_data_service.option_rows = [
        {
            "strike": 22500,
            "is_atm": True,
            "call": market_data_service.quotes["NIFTY_2026-03-12_22500_CE"],
            "put": {
                "symbol": "NIFTY_2026-03-12_22500_PE",
                "security_id": "54321",
                "strike": 22500,
                "option_type": "PE",
                "expiry": "2026-03-12",
                "ltp": 95.0,
                "bid": 94.8,
                "ask": 95.2,
                "bid_qty": 420,
                "ask_qty": 410,
                "oi": 110000,
                "oi_lakhs": 1.1,
                "volume": 18000,
            },
        }
    ]
    market_data_service._security_id_to_symbol = {"12345": "NIFTY_2026-03-12_22500_CE"}
    market_data_service._dirty_quote_symbols.clear()
    market_data_service._snapshot_dirty = False

    market_data_service._handle_feed_packet({"type": "Quote Data", "security_id": 13, "LTP": "22555.25", "close": "22450.00"})
    assert market_data_service.snapshot["spot"] == 22555.25
    assert market_data_service.snapshot["change"] == 105.25
    assert market_data_service._snapshot_dirty is True

    market_data_service._handle_feed_packet(
        {
            "type": "Full Data",
            "security_id": 12345,
            "LTP": "118.50",
            "volume": 26000,
            "OI": 120000,
            "depth": [
                {
                    "bid_price": "118.40",
                    "ask_price": "118.55",
                    "bid_quantity": 650,
                    "ask_quantity": 600,
                }
            ],
        }
    )
    quote = market_data_service.quotes["NIFTY_2026-03-12_22500_CE"]
    assert quote["ltp"] == 118.5
    assert quote["bid"] == 118.4
    assert quote["ask"] == 118.55
    assert quote["oi_lakhs"] == 1.2
    assert quote["volume"] == 26000
    assert "NIFTY_2026-03-12_22500_CE" in market_data_service._dirty_quote_symbols

    batch = market_data_service._build_quote_batch(("NIFTY_2026-03-12_22500_CE",))
    assert batch["quotes"][0]["symbol"] == "NIFTY_2026-03-12_22500_CE"
    assert batch["quotes"][0]["ltp"] == 118.5


def test_build_feed_instruments_includes_vix() -> None:
    """VIX (security_id 21) should be subscribed on the WebSocket feed."""
    _reset_test_runtime()
    market_data_service.reset_runtime_state_for_tests()
    market_data_service.quotes = {
        "NIFTY_2026-03-26_24000_CE": {"security_id": "12345"},
    }

    instruments = market_data_service._build_feed_instruments()
    security_ids = {sid for _, sid, _ in instruments}
    assert "21" in security_ids, f"VIX security_id 21 should be in feed instruments, got {security_ids}"


def test_fetch_candles_returns_full_intraday_window_without_legacy_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    base = int(datetime(2026, 3, 10, 3, 45, tzinfo=timezone.utc).timestamp())
    timestamps = [base + index * 900 for index in range(600)]

    class FakeDhanClient:
        def intraday_minute_data(self, **kwargs):
            self.last_kwargs = kwargs
            return {
                "data": {
                    "timestamp": timestamps,
                    "open": [22000 + index for index in range(600)],
                    "high": [22001 + index for index in range(600)],
                    "low": [21999 + index for index in range(600)],
                    "close": [22000.5 + index for index in range(600)],
                    "volume": [1000 + index for index in range(600)],
                }
            }

    fake_client = FakeDhanClient()
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(dhan_credential_service, "call", lambda operation_name, fn, **kwargs: fn(fake_client)["data"])

    response = market_data_service._fetch_candles("15m")

    assert len(response["candles"]) == 600
    assert response["candles"][0]["time"] == timestamps[0]
    assert response["candles"][-1]["time"] == timestamps[-1]
    assert response["has_more"] is True
    assert response["next_before"] == timestamps[0]
    assert fake_client.last_kwargs["interval"] == 15


def test_seed_spot_from_history_preserves_live_spot_when_backfilling_prev_close(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    market_data_service.last_known_spot = 22555.25
    market_data_service.snapshot["spot"] = 22555.25
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 21, 10, 0, tzinfo=market_hours.IST),
    )

    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: {
            "timestamp": [
                "2026-03-19T00:00:00+00:00",
                "2026-03-20T00:00:00+00:00",
            ],
            "close": [22450.0, 22500.0],
        },
    )
    monkeypatch.setattr(market_data_module, "is_market_open", lambda: True)

    asyncio.run(market_data_service._seed_spot_from_history())

    assert market_data_service.snapshot["spot"] == 22555.25
    assert market_data_service.last_known_spot == 22555.25
    assert market_data_service.last_known_prev_close == 22500.0
    assert market_data_service.snapshot["change"] == 55.25
    assert market_data_service.snapshot["change_pct"] == 0.25


def test_seed_spot_from_history_uses_last_two_daily_closes_when_live_spot_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    market_data_service.last_known_spot = 0.0
    market_data_service.snapshot["spot"] = 0.0

    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: {
            "timestamp": [
                "2026-03-19T00:00:00+00:00",
                "2026-03-20T00:00:00+00:00",
            ],
            "close": [22450.0, 22500.0],
        },
    )
    monkeypatch.setattr(market_data_module, "is_market_open", lambda: False)

    asyncio.run(market_data_service._seed_spot_from_history())

    assert market_data_service.snapshot["spot"] == 22500.0
    assert market_data_service.last_known_spot == 22500.0
    assert market_data_service.last_known_prev_close == 22450.0
    assert market_data_service.snapshot["change"] == 50.0
    assert market_data_service.snapshot["change_pct"] == 0.22


def test_seed_vix_from_history_uses_last_daily_close(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    market_data_service.snapshot["vix"] = None

    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: {
            "timestamp": [
                "2026-03-19T00:00:00+00:00",
                "2026-03-20T00:00:00+00:00",
            ],
            "close": [13.4, 14.1],
        },
    )

    asyncio.run(market_data_service._seed_vix_from_history())

    assert market_data_service.snapshot["vix"] == 14.1
    assert market_data_service.last_vix_refresh is not None


def test_fetch_expiries_normalizes_sorts_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: {
            "data": [
                {"expiryDate": "2026-03-26T10:00:00+05:30"},
                {"expiry": "2026-03-19"},
                "2026-03-12",
                {"expiry_date": "2026-03-19"},
            ]
        },
    )

    expiries = market_data_service._fetch_expiries()

    assert expiries == ["2026-03-12", "2026-03-19", "2026-03-26"]


def test_fetch_option_chain_rounds_half_up_for_atm_strike(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    market_data_service.last_known_spot = 22525.0

    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: {
            "data": {
                "last_price": 22525.0,
                "oc": {
                    "22500": {
                        "ce": {"security_id": "1001", "last_price": 101.0},
                        "pe": {"security_id": "1002", "last_price": 121.0},
                    },
                    "22550": {
                        "ce": {"security_id": "1003", "last_price": 82.0},
                        "pe": {"security_id": "1004", "last_price": 140.0},
                    },
                },
            }
        },
    )

    chain = market_data_service._fetch_option_chain("2026-03-26")

    assert chain is not None
    assert [(row["strike"], row["is_atm"]) for row in chain["rows"]] == [
        (22500, False),
        (22550, True),
    ]


def test_get_option_chain_uses_live_spot_for_atm_between_chain_refreshes() -> None:
    _reset_test_runtime()
    market_data_service.last_known_spot = 22525.0
    market_data_service.option_rows = [
        {
            "strike": 22500,
            "is_atm": True,
            "call": {"symbol": "NIFTY_2026-03-26_22500_CE", "strike": 22500, "option_type": "CE", "expiry": "2026-03-26", "ltp": 101.0},
            "put": {"symbol": "NIFTY_2026-03-26_22500_PE", "strike": 22500, "option_type": "PE", "expiry": "2026-03-26", "ltp": 121.0},
        },
        {
            "strike": 22550,
            "is_atm": False,
            "call": {"symbol": "NIFTY_2026-03-26_22550_CE", "strike": 22550, "option_type": "CE", "expiry": "2026-03-26", "ltp": 82.0},
            "put": {"symbol": "NIFTY_2026-03-26_22550_PE", "strike": 22550, "option_type": "PE", "expiry": "2026-03-26", "ltp": 140.0},
        },
    ]

    response = market_data_service.get_option_chain()

    assert [(row.strike, row.is_atm) for row in response.rows] == [
        (22500, False),
        (22550, True),
    ]


def test_get_option_chain_allows_missing_ltp_without_crashing() -> None:
    _reset_test_runtime()
    market_data_service.option_rows = [
        {
            "strike": 22500,
            "is_atm": True,
            "call": {
                "symbol": "NIFTY_2026-03-26_22500_CE",
                "strike": 22500,
                "option_type": "CE",
                "expiry": "2026-03-26",
                "ltp": None,
            },
            "put": {
                "symbol": "NIFTY_2026-03-26_22500_PE",
                "strike": 22500,
                "option_type": "PE",
                "expiry": "2026-03-26",
                "ltp": 121.0,
            },
        }
    ]

    response = market_data_service.get_option_chain()

    assert response.rows[0].call.ltp is None
    assert response.rows[0].put.ltp == 121.0


def test_apply_index_tick_marks_chain_dirty_when_live_atm_changes() -> None:
    _reset_test_runtime()
    market_data_service._active_atm_strike = 22500
    market_data_service._chain_dirty = False

    market_data_service._apply_index_tick(
        {
            "type": "Full Data",
            "security_id": 13,
            "LTP": "22525.00",
            "close": "22450.00",
        }
    )

    assert market_data_service._active_atm_strike == 22550
    assert market_data_service._chain_dirty is True


def test_fetch_daily_candles_does_not_create_phantom_current_day_before_open(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    market_data_service.last_known_spot = 22500.0
    market_data_service.snapshot["spot"] = 22500.0
    market_data_service.snapshot["day_high"] = None
    market_data_service.snapshot["day_low"] = None

    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 13, 8, 45, tzinfo=market_hours.IST),
    )
    monkeypatch.setattr(market_data_module, "is_trading_day", lambda: True)

    operations: list[str] = []

    def fake_call(operation_name, fn, **kwargs):
        operations.append(operation_name)
        if operation_name == "chart_historical_daily_data":
            return {
                "timestamp": ["2026-03-12T00:00:00+00:00"],
                "open": [22400.0],
                "high": [22510.0],
                "low": [22380.0],
                "close": [22480.0],
                "volume": [1000],
            }
        if operation_name == "intraday_minute_data":
            return {"timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
        raise AssertionError(f"Unexpected operation: {operation_name}")

    monkeypatch.setattr(dhan_credential_service, "call", fake_call)

    response = market_data_service._fetch_candles("D")

    assert operations == ["chart_historical_daily_data", "intraday_minute_data"]
    assert [candle["time"] for candle in response["candles"]] == [
        int(datetime(2026, 3, 12, tzinfo=market_hours.IST).timestamp()),
    ]
    assert response["candles"][0]["open"] == 22400.0
    assert response["candles"][0]["close"] == 22480.0


def test_fetch_daily_candles_builds_current_session_bar_from_intraday_history(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    market_data_service.last_known_spot = 22535.0
    market_data_service.snapshot["spot"] = 22535.0
    market_data_service.snapshot["day_high"] = 22540.0
    market_data_service.snapshot["day_low"] = 22500.0

    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 13, 10, 30, tzinfo=market_hours.IST),
    )
    monkeypatch.setattr(market_data_module, "is_trading_day", lambda: True)

    def fake_call(operation_name, fn, **kwargs):
        if operation_name == "chart_historical_daily_data":
            return {
                "timestamp": ["2026-03-12T00:00:00+00:00"],
                "open": [22400.0],
                "high": [22510.0],
                "low": [22380.0],
                "close": [22480.0],
                "volume": [1000],
            }
        if operation_name == "intraday_minute_data":
            return {
                "timestamp": [
                    "2026-03-13T03:45:00+00:00",
                    "2026-03-13T03:46:00+00:00",
                    "2026-03-13T03:47:00+00:00",
                ],
                "open": [22510.0, 22512.0, 22515.0],
                "high": [22520.0, 22525.0, 22530.0],
                "low": [22505.0, 22510.0, 22514.0],
                "close": [22518.0, 22520.0, 22528.0],
                "volume": [100, 120, 130],
            }
        raise AssertionError(f"Unexpected operation: {operation_name}")

    monkeypatch.setattr(dhan_credential_service, "call", fake_call)

    response = market_data_service._fetch_candles("D")

    assert len(response["candles"]) == 2
    assert response["candles"][-1] == {
        "time": int(datetime(2026, 3, 13, tzinfo=market_hours.IST).timestamp()),
        "open": 22510.0,
        "high": 22540.0,
        "low": 22500.0,
        "close": 22535.0,
        "volume": 350.0,
    }


def test_fetch_daily_candles_reapplies_live_overlay_when_session_cache_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    market_data_service.last_known_spot = 22520.0
    market_data_service.snapshot["spot"] = 22520.0
    market_data_service.snapshot["day_high"] = 22530.0
    market_data_service.snapshot["day_low"] = 22505.0

    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 13, 10, 30, tzinfo=market_hours.IST),
    )
    monkeypatch.setattr(market_data_module, "is_trading_day", lambda: True)

    call_count = {"intraday": 0}

    def fake_call(operation_name, fn, **kwargs):
        if operation_name == "chart_historical_daily_data":
            return {
                "timestamp": ["2026-03-12T00:00:00+00:00"],
                "open": [22400.0],
                "high": [22510.0],
                "low": [22380.0],
                "close": [22480.0],
                "volume": [1000],
            }
        if operation_name == "intraday_minute_data":
            call_count["intraday"] += 1
            return {
                "timestamp": [
                    "2026-03-13T03:45:00+00:00",
                    "2026-03-13T03:46:00+00:00",
                ],
                "open": [22510.0, 22512.0],
                "high": [22520.0, 22525.0],
                "low": [22505.0, 22510.0],
                "close": [22518.0, 22520.0],
                "volume": [100, 120],
            }
        raise AssertionError(f"Unexpected operation: {operation_name}")

    monkeypatch.setattr(dhan_credential_service, "call", fake_call)

    first = market_data_service._fetch_candles("D")
    assert first["candles"][-1]["close"] == 22520.0
    assert first["candles"][-1]["high"] == 22530.0
    assert call_count["intraday"] == 1

    market_data_service.last_known_spot = 22542.0
    market_data_service.snapshot["spot"] = 22542.0
    market_data_service.snapshot["day_high"] = 22548.0
    market_data_service.snapshot["day_low"] = 22500.0

    second = market_data_service._fetch_candles("D")

    assert call_count["intraday"] == 1
    assert second["candles"][-1] == {
        "time": int(datetime(2026, 3, 13, tzinfo=market_hours.IST).timestamp()),
        "open": 22510.0,
        "high": 22548.0,
        "low": 22500.0,
        "close": 22542.0,
        "volume": 220.0,
    }


def test_fetch_candles_aggregates_weekly_and_monthly_from_daily_history(monkeypatch: pytest.MonkeyPatch) -> None:
    timestamps = [
        "2026-01-26T00:00:00+00:00",
        "2026-01-27T00:00:00+00:00",
        "2026-01-28T00:00:00+00:00",
        "2026-01-29T00:00:00+00:00",
        "2026-01-30T00:00:00+00:00",
        "2026-02-02T00:00:00+00:00",
        "2026-02-03T00:00:00+00:00",
    ]

    class FakeDhanClient:
        def historical_daily_data(self, **kwargs):
            self.last_kwargs = kwargs
            return {
                "data": {
                    "timestamp": timestamps,
                    "open": [100.0, 101.0, 102.0, 103.0, 104.0, 110.0, 111.0],
                    "high": [101.0, 105.0, 103.0, 106.0, 107.0, 112.0, 115.0],
                    "low": [99.0, 100.0, 101.0, 102.0, 103.0, 109.0, 110.0],
                    "close": [100.5, 104.0, 102.5, 105.0, 106.5, 111.0, 114.0],
                    "volume": [10, 20, 30, 40, 50, 60, 70],
                }
            }

    fake_client = FakeDhanClient()
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(dhan_credential_service, "call", lambda operation_name, fn, **kwargs: fn(fake_client)["data"])
    monkeypatch.setattr(market_data_service, "_live_ohlc_for_target", lambda target: (None, None, None))

    weekly = market_data_service._fetch_candles("W")
    monthly = market_data_service._fetch_candles("M")

    ist = timezone(timedelta(hours=5, minutes=30))
    assert [candle["time"] for candle in weekly["candles"]] == [
        int(datetime(2026, 1, 26, tzinfo=ist).timestamp()),
        int(datetime(2026, 2, 2, tzinfo=ist).timestamp()),
    ]
    assert weekly["candles"][0]["open"] == 100.0
    assert weekly["candles"][0]["high"] == 107.0
    assert weekly["candles"][0]["low"] == 99.0
    assert weekly["candles"][0]["close"] == 106.5
    assert weekly["candles"][0]["volume"] == 150.0
    assert weekly["candles"][1]["close"] == 114.0
    assert weekly["candles"][1]["volume"] == 130.0

    assert [candle["time"] for candle in monthly["candles"]] == [
        int(datetime(2026, 1, 1, tzinfo=ist).timestamp()),
        int(datetime(2026, 2, 1, tzinfo=ist).timestamp()),
    ]
    assert monthly["candles"][0]["open"] == 100.0
    assert monthly["candles"][0]["high"] == 107.0
    assert monthly["candles"][0]["low"] == 99.0
    assert monthly["candles"][0]["close"] == 106.5
    assert monthly["candles"][0]["volume"] == 150.0
    assert monthly["candles"][1]["close"] == 114.0
    assert monthly["candles"][1]["volume"] == 130.0
    assert fake_client.last_kwargs["instrument_type"] == "INDEX"


def test_apply_index_tick_updates_day_extremes_even_when_price_is_unchanged() -> None:
    _reset_test_runtime()
    market_data_service.last_known_prev_close = 22450.0
    market_data_service.snapshot["spot"] = 22555.25
    market_data_service.snapshot["change"] = 105.25
    market_data_service.snapshot["change_pct"] = 0.47
    market_data_service.snapshot["day_high"] = 22560.0
    market_data_service.snapshot["day_low"] = 22440.0
    market_data_service._snapshot_dirty = False

    market_data_service._apply_index_tick(
        {
            "type": "Full Data",
            "security_id": 13,
            "LTP": "22555.25",
            "close": "22450.00",
            "high": "22580.00",
            "low": "22430.00",
        }
    )

    assert market_data_service.snapshot["spot"] == 22555.25
    assert market_data_service.snapshot["change"] == 105.25
    assert market_data_service.snapshot["day_high"] == 22580.0
    assert market_data_service.snapshot["day_low"] == 22430.0
    assert market_data_service._snapshot_dirty is True


def test_market_candles_route_supports_before_cursor(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    timestamps = [
        int(datetime(2026, 3, 9, 3, 45, tzinfo=timezone.utc).timestamp()),
        int(datetime(2026, 3, 9, 4, 0, tzinfo=timezone.utc).timestamp()),
        int(datetime(2026, 3, 9, 4, 15, tzinfo=timezone.utc).timestamp()),
    ]

    class FakeDhanClient:
        def intraday_minute_data(self, **kwargs):
            return {
                "data": {
                    "timestamp": timestamps,
                    "open": [22400.0, 22410.0, 22420.0],
                    "high": [22405.0, 22415.0, 22425.0],
                    "low": [22395.0, 22405.0, 22415.0],
                    "close": [22402.0, 22412.0, 22422.0],
                    "volume": [100, 120, 140],
                }
            }

    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    fake_client = FakeDhanClient()
    monkeypatch.setattr(dhan_credential_service, "call", lambda operation_name, fn, **kwargs: fn(fake_client)["data"])

    response = client.get(
        f"/api/v1/market/candles?timeframe=15m&before={timestamps[1]}",
        headers=headers,
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert [candle["time"] for candle in payload["candles"]] == [timestamps[0]]
    assert payload["has_more"] is True
    assert payload["next_before"] == timestamps[0]


def test_fetch_candles_resolves_option_symbol_via_option_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    symbol = "NIFTY_2026-03-19_22450_PE"
    timestamps = [
        int(datetime(2026, 3, 10, 3, 45, tzinfo=timezone.utc).timestamp()),
        int(datetime(2026, 3, 10, 4, 0, tzinfo=timezone.utc).timestamp()),
    ]

    class FakeDhanClient:
        def intraday_minute_data(self, **kwargs):
            self.last_kwargs = kwargs
            return {
                "data": {
                    "timestamp": timestamps,
                    "open": [85.0, 86.0],
                    "high": [86.0, 87.0],
                    "low": [84.5, 85.5],
                    "close": [85.5, 86.5],
                    "volume": [1000, 1100],
                }
            }

    fake_client = FakeDhanClient()
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(dhan_credential_service, "call", lambda operation_name, fn, **kwargs: fn(fake_client)["data"])
    monkeypatch.setattr(
        market_data_service,
        "_fetch_option_chain_cached",
        lambda expiry: pytest.fail("symbol lookup should not fetch option-chain data"),
    )
    market_data_service._option_metadata[symbol] = market_data_module.CandleInstrument(
        symbol=symbol,
        security_id="778899",
        exchange_segment="NSE_FNO",
        instrument_type="OPTIDX",
    )

    response = market_data_service._fetch_candles("15m", symbol=symbol)

    assert [candle["time"] for candle in response["candles"]] == timestamps
    assert fake_client.last_kwargs["security_id"] == "778899"
    assert fake_client.last_kwargs["exchange_segment"] == "NSE_FNO"
    assert fake_client.last_kwargs["instrument_type"] == "OPTIDX"


def test_fetch_candles_resolves_option_symbol_via_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    symbol = "NIFTY_2026-03-19_22450_PE"
    observed_at = datetime(2026, 3, 19, 9, 15, tzinfo=timezone.utc)
    with SessionLocal() as db:
        db.add(
            DhanInstrumentRegistry(
                symbol=symbol,
                security_id="778899",
                root_symbol="NIFTY",
                exchange_segment="NSE_FNO",
                instrument_type="OPTIDX",
                expiry="2026-03-19",
                strike=22450,
                option_type="PE",
                first_seen=observed_at,
                last_seen=observed_at,
            )
        )
        db.commit()

    timestamps = [
        int(datetime(2026, 3, 10, 3, 45, tzinfo=timezone.utc).timestamp()),
        int(datetime(2026, 3, 10, 4, 0, tzinfo=timezone.utc).timestamp()),
    ]

    class FakeDhanClient:
        def intraday_minute_data(self, **kwargs):
            self.last_kwargs = kwargs
            return {
                "data": {
                    "timestamp": timestamps,
                    "open": [85.0, 86.0],
                    "high": [86.0, 87.0],
                    "low": [84.5, 85.5],
                    "close": [85.5, 86.5],
                    "volume": [1000, 1100],
                }
            }

    fake_client = FakeDhanClient()
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(dhan_credential_service, "call", lambda operation_name, fn, **kwargs: fn(fake_client)["data"])
    monkeypatch.setattr(
        market_data_service,
        "_fetch_option_chain_cached",
        lambda expiry: pytest.fail("registry-backed symbol lookup should not fetch option-chain data"),
    )

    response = market_data_service._fetch_candles("15m", symbol=symbol)

    assert [candle["time"] for candle in response["candles"]] == timestamps
    assert fake_client.last_kwargs["security_id"] == "778899"
    assert fake_client.last_kwargs["exchange_segment"] == "NSE_FNO"
    assert fake_client.last_kwargs["instrument_type"] == "OPTIDX"


def test_fetch_candles_uses_supplied_security_id_for_option_symbol_without_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    symbol = "NIFTY_2026-03-26_22500_CE"
    timestamps = [
        int(datetime(2026, 3, 10, 3, 45, tzinfo=timezone.utc).timestamp()),
        int(datetime(2026, 3, 10, 4, 0, tzinfo=timezone.utc).timestamp()),
    ]

    class FakeDhanClient:
        def intraday_minute_data(self, **kwargs):
            self.last_kwargs = kwargs
            return {
                "data": {
                    "timestamp": timestamps,
                    "open": [110.0, 111.0],
                    "high": [111.0, 112.0],
                    "low": [109.5, 110.5],
                    "close": [110.5, 111.5],
                    "volume": [2000, 2100],
                }
            }

    fake_client = FakeDhanClient()
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(dhan_credential_service, "call", lambda operation_name, fn, **kwargs: fn(fake_client)["data"])
    monkeypatch.setattr(
        market_data_service,
        "_fetch_option_chain_cached",
        lambda expiry: pytest.fail("security-id backed lookup should not fetch option-chain data"),
    )

    response = market_data_service._fetch_candles("15m", symbol=symbol, security_id="98765")

    assert [candle["time"] for candle in response["candles"]] == timestamps
    assert fake_client.last_kwargs["security_id"] == "98765"
    assert fake_client.last_kwargs["exchange_segment"] == "NSE_FNO"
    assert fake_client.last_kwargs["instrument_type"] == "OPTIDX"


def test_market_candles_route_rejects_option_symbol_without_cached_metadata_without_fetching_chain(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    symbol = "NIFTY_2026-03-19_22450_PE"
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(
        market_data_service,
        "_fetch_option_chain_cached",
        lambda expiry: pytest.fail("option symbol lookup should not fetch option-chain data"),
    )
    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: pytest.fail("symbol lookup should not hit Dhan"),
    )

    response = client.get(
        f"/api/v1/market/candles?timeframe=15m&symbol={symbol}",
        headers=headers,
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "SYMBOL_NOT_AVAILABLE"


def test_market_candles_route_supports_option_symbol(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    symbol = "NIFTY_2026-03-12_22500_CE"
    timestamps = [
        int(datetime(2026, 3, 10, 3, 45, tzinfo=timezone.utc).timestamp()),
        int(datetime(2026, 3, 10, 4, 0, tzinfo=timezone.utc).timestamp()),
    ]

    class FakeDhanClient:
        def intraday_minute_data(self, **kwargs):
            self.last_kwargs = kwargs
            return {
                "data": {
                    "timestamp": timestamps,
                    "open": [110.0, 111.0],
                    "high": [111.0, 112.0],
                    "low": [109.5, 110.5],
                    "close": [110.5, 111.5],
                    "volume": [2000, 2100],
                }
            }

    fake_client = FakeDhanClient()
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(dhan_credential_service, "call", lambda operation_name, fn, **kwargs: fn(fake_client)["data"])
    market_data_service.quotes[symbol] = {
        "symbol": symbol,
        "security_id": "12345",
        "strike": 22500,
        "option_type": "CE",
        "expiry": "2026-03-12",
        "ltp": 111.5,
        "bid": 111.0,
        "ask": 112.0,
        "bid_qty": 500,
        "ask_qty": 450,
        "oi": 100000,
        "volume": 25000,
    }
    market_data_service._security_id_to_symbol = {"12345": symbol}

    response = client.get(
        f"/api/v1/market/candles?timeframe=15m&symbol={symbol}",
        headers=headers,
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert [candle["time"] for candle in payload["candles"]] == timestamps
    assert fake_client.last_kwargs["security_id"] == "12345"
    assert fake_client.last_kwargs["exchange_segment"] == "NSE_FNO"
    assert fake_client.last_kwargs["instrument_type"] == "OPTIDX"


def test_market_candles_route_rejects_unsupported_symbol_format(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)

    response = client.get(
        "/api/v1/market/candles?timeframe=15m&symbol=BAD_SYMBOL",
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported symbol format. Expected NIFTY 50, INDIA VIX/VIX, or NIFTY_YYYY-MM-DD_STRIKE_CE|PE"


def test_market_candles_route_supports_vix_aliases(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    timestamps = [
        "2026-03-19T00:00:00+00:00",
        "2026-03-20T00:00:00+00:00",
    ]

    class FakeDhanClient:
        def historical_daily_data(self, **kwargs):
            self.last_kwargs = kwargs
            return {
                "data": {
                    "timestamp": timestamps,
                    "open": [13.1, 13.8],
                    "high": [13.6, 14.2],
                    "low": [12.9, 13.5],
                    "close": [13.4, 14.1],
                    "volume": [0, 0],
                }
            }

    fake_client = FakeDhanClient()
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(dhan_credential_service, "call", lambda operation_name, fn, **kwargs: fn(fake_client)["data"])

    response = client.get("/api/v1/market/candles?timeframe=D&symbol=VIX", headers=headers)

    assert response.status_code == 200, response.text
    assert fake_client.last_kwargs["security_id"] == "21"
    assert response.json()["candles"][-1]["close"] == 14.1


def test_current_bucket_time_supports_intraday_intervals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 12, 10, 7, tzinfo=market_hours.IST),
    )

    bucket = market_data_service._current_bucket_time("15m")
    expected = int(datetime(2026, 3, 12, 10, 0, tzinfo=market_hours.IST).timestamp())
    assert bucket == expected


def test_overlay_live_price_creates_intraday_candle_without_day_extremes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Intraday new-bucket candle must use live_price, NOT day_high/day_low.

    A new 15m candle should be created from the live price (so the chart
    shows current data), but day_high/day_low must not inflate its wicks.
    """
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 13, 9, 16, tzinfo=market_hours.IST),
    )
    monkeypatch.setattr(market_hours, "is_trading_day", lambda: True)
    candles = [
        {
            "time": int(datetime(2026, 3, 13, 9, 0, tzinfo=market_hours.IST).timestamp()),
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 1000.0,
        }
    ]

    result = market_data_service._overlay_live_price(
        candles,
        timeframe="15m",
        live_price=103.5,
        day_high=110.0,
        day_low=95.0,
    )

    # New candle created for current bucket with live price
    assert len(result) == 2
    new_candle = result[-1]
    assert new_candle["close"] == 103.5
    # day_high/day_low must NOT be applied — wicks stay within live price range
    assert new_candle["high"] == 103.5
    assert new_candle["low"] == 101.0  # open_price from prev candle close


def test_overlay_live_price_ignores_day_extremes_for_intraday_matching_candle(monkeypatch: pytest.MonkeyPatch) -> None:
    """When updating a matching intraday candle, day_high/day_low must be ignored.

    The full-session range doesn't belong in a single 5m/15m/1h bar.
    """
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 13, 10, 17, tzinfo=market_hours.IST),
    )
    bucket_time = int(datetime(2026, 3, 13, 10, 15, tzinfo=market_hours.IST).timestamp())
    candles = [
        {
            "time": bucket_time,
            "open": 22300.0,
            "high": 22310.0,
            "low": 22290.0,
            "close": 22305.0,
            "volume": 5000.0,
        }
    ]

    result = market_data_service._overlay_live_price(
        candles,
        timeframe="15m",
        live_price=22308.0,
        day_high=22500.0,
        day_low=21800.0,
    )

    assert len(result) == 1
    updated = result[0]
    assert updated["close"] == 22308.0
    # high/low should reflect only the live price, NOT the day's extremes
    assert updated["high"] == 22310.0  # unchanged — live price didn't exceed interval high
    assert updated["low"] == 22290.0   # unchanged — live price didn't go below interval low


def test_overlay_live_price_applies_day_extremes_for_daily_candle(monkeypatch: pytest.MonkeyPatch) -> None:
    """For daily candles, day_high/day_low SHOULD be applied."""
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 13, 10, 30, tzinfo=market_hours.IST),
    )
    bucket_time = int(datetime(2026, 3, 13, 0, 0, tzinfo=market_hours.IST).timestamp())
    candles = [
        {
            "time": bucket_time,
            "open": 22300.0,
            "high": 22310.0,
            "low": 22290.0,
            "close": 22305.0,
            "volume": 5000.0,
        }
    ]

    result = market_data_service._overlay_live_price(
        candles,
        timeframe="D",
        live_price=22308.0,
        day_high=22500.0,
        day_low=21800.0,
    )

    assert len(result) == 1
    updated = result[0]
    assert updated["close"] == 22308.0
    assert updated["high"] == 22500.0  # day_high applied
    assert updated["low"] == 21800.0   # day_low applied


def test_overlay_live_price_does_not_override_closed_daily_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 13, 16, 10, tzinfo=market_hours.IST),
    )
    bucket_time = int(datetime(2026, 3, 13, 0, 0, tzinfo=market_hours.IST).timestamp())
    candles = [
        {
            "time": bucket_time,
            "open": 22300.0,
            "high": 22500.0,
            "low": 22290.0,
            "close": 22305.0,
            "volume": 5000.0,
        }
    ]

    result = market_data_service._overlay_live_price(
        candles,
        timeframe="D",
        live_price=22380.0,
        day_high=22600.0,
        day_low=22100.0,
    )

    assert result == candles


def test_build_live_session_candle_keeps_session_close_after_market_close(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    monkeypatch.setattr(
        market_hours,
        "now_ist",
        lambda: datetime(2026, 3, 13, 16, 5, tzinfo=market_hours.IST),
    )

    payload = {
        "timestamp": [
            "2026-03-13T09:15:00+05:30",
            "2026-03-13T15:29:00+05:30",
        ],
        "open": [22300.0, 22308.0],
        "high": [22320.0, 22340.0],
        "low": [22290.0, 22300.0],
        "close": [22310.0, 22325.0],
        "volume": [1000.0, 2000.0],
    }

    monkeypatch.setattr("services.market_data.dhan_credential_service.call", lambda *args, **kwargs: payload)
    market_data_service._live_session_candle_cache.clear()

    target = market_data_service._resolve_candle_target(symbol="NIFTY 50", security_id=None)
    candle = market_data_service._build_live_session_candle(
        target,
        timeframe="D",
        live_price=22380.0,
        day_high=22420.0,
        day_low=22280.0,
    )

    assert candle is not None
    assert candle["close"] == 22325.0
    assert candle["high"] == 22420.0
    assert candle["low"] == 22280.0


def test_get_candles_maps_rate_limit_and_invalid_request_to_specific_status_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)

    def raise_rate_limit(*args, **kwargs):
        raise DhanApiError("DHAN_RATE_LIMITED", "Too many requests")

    monkeypatch.setattr(market_data_service, "_fetch_candles", raise_rate_limit)
    with pytest.raises(market_data_module.CandleQueryError) as rate_limited:
        asyncio.run(market_data_service.get_candles("15m"))
    assert rate_limited.value.status_code == 429
    assert rate_limited.value.detail == "DHAN_RATE_LIMITED"

    def raise_invalid_request(*args, **kwargs):
        raise DhanApiError("DHAN_INVALID_REQUEST", "Invalid Expiry Date")

    monkeypatch.setattr(market_data_service, "_fetch_candles", raise_invalid_request)
    with pytest.raises(market_data_module.CandleQueryError) as invalid_request:
        asyncio.run(market_data_service.get_candles("15m"))
    assert invalid_request.value.status_code == 400
    assert invalid_request.value.detail == "DHAN_INVALID_REQUEST"


def test_fetch_candles_no_data_keeps_paging_for_older_option_history(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    symbol = "NIFTY_2025-01-30_22500_CE"
    observed_at = datetime(2025, 1, 10, 9, 15, tzinfo=timezone.utc)
    with SessionLocal() as db:
        db.add(
            DhanInstrumentRegistry(
                symbol=symbol,
                security_id="55555",
                root_symbol="NIFTY",
                exchange_segment="NSE_FNO",
                instrument_type="OPTIDX",
                expiry="2025-01-30",
                strike=22500,
                option_type="CE",
                first_seen=observed_at,
                last_seen=observed_at,
            )
        )
        db.commit()

    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: (_ for _ in ()).throw(DhanApiError("DHAN_NO_DATA", "No data present")),
    )

    response = market_data_service._fetch_candles("D", symbol=symbol)

    assert response["candles"] == []
    assert response["degraded"] is False
    assert response["has_more"] is True
    assert response["next_before"] is not None


def test_fetch_candles_cached_no_data_stays_non_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    symbol = "NIFTY_2025-01-30_22500_CE"
    observed_at = datetime(2025, 1, 10, 9, 15, tzinfo=timezone.utc)
    with SessionLocal() as db:
        db.add(
            DhanInstrumentRegistry(
                symbol=symbol,
                security_id="55555",
                root_symbol="NIFTY",
                exchange_segment="NSE_FNO",
                instrument_type="OPTIDX",
                expiry="2025-01-30",
                strike=22500,
                option_type="CE",
                first_seen=observed_at,
                last_seen=observed_at,
            )
        )
        db.commit()

    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    calls = {"count": 0}

    def fake_call(operation_name, fn, **kwargs):
        calls["count"] += 1
        raise DhanApiError("DHAN_NO_DATA", "No data present")

    monkeypatch.setattr(dhan_credential_service, "call", fake_call)

    first = market_data_service._fetch_candles("D", symbol=symbol)
    second = market_data_service._fetch_candles("D", symbol=symbol)

    assert calls["count"] == 1
    assert first["degraded"] is False
    assert second["degraded"] is False


def test_fetch_candles_no_data_can_overlay_live_intraday_option_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    symbol = "NIFTY_2026-03-12_22500_CE"
    market_data_service.quotes[symbol] = {
        "symbol": symbol,
        "security_id": "12345",
        "strike": 22500,
        "option_type": "CE",
        "expiry": "2026-03-12",
        "ltp": 111.5,
        "bid": 111.0,
        "ask": 112.0,
        "bid_qty": 500,
        "ask_qty": 450,
        "oi": 100000,
        "volume": 25000,
        "day_high": 112.0,
        "day_low": 110.5,
    }
    market_data_service._security_id_to_symbol = {"12345": symbol}
    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: (_ for _ in ()).throw(DhanApiError("DHAN_NO_DATA", "No data present")),
    )

    response = market_data_service._fetch_candles("15m", symbol=symbol)

    assert len(response["candles"]) == 1
    assert response["candles"][0]["close"] == 111.5
    assert response["degraded"] is False


def test_fetch_candles_does_not_persist_untrusted_symbol_security_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    symbol = "NIFTY_2026-03-26_22500_CE"
    timestamps = [
        "2026-03-19T00:00:00+00:00",
        "2026-03-20T00:00:00+00:00",
    ]

    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: {
            "timestamp": timestamps,
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000, 1100],
        },
    )

    market_data_service._fetch_candles("D", symbol=symbol, security_id="99999")

    with SessionLocal() as db:
        record = db.query(DhanInstrumentRegistry).filter(DhanInstrumentRegistry.symbol == symbol).one_or_none()
    assert record is None


def test_weekly_option_history_does_not_move_registry_first_seen_backward(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    symbol = "NIFTY_2026-03-24_23300_PE"
    first_seen = datetime(2026, 3, 19, 0, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        db.add(
            DhanInstrumentRegistry(
                symbol=symbol,
                security_id="62589",
                root_symbol="NIFTY",
                exchange_segment="NSE_FNO",
                instrument_type="OPTIDX",
                expiry="2026-03-24",
                strike=23300,
                option_type="PE",
                first_seen=first_seen,
                last_seen=first_seen,
            )
        )
        db.commit()

    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(
        dhan_credential_service,
        "call",
        lambda operation_name, fn, **kwargs: {
            "timestamp": [
                "2026-03-19T00:00:00+00:00",
                "2026-03-20T00:00:00+00:00",
            ],
            "open": [210.0, 220.0],
            "high": [215.0, 225.0],
            "low": [205.0, 215.0],
            "close": [212.0, 221.0],
            "volume": [1000, 1200],
        },
    )

    market_data_service._fetch_candles("W", symbol=symbol)

    with SessionLocal() as db:
        record = db.query(DhanInstrumentRegistry).filter(DhanInstrumentRegistry.symbol == symbol).one()
    assert record.first_seen.replace(tzinfo=timezone.utc) == first_seen


def test_dhan_credential_service_regenerates_token_via_totp(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    now = datetime(2026, 3, 14, 3, 45, tzinfo=timezone.utc)
    expired_token = _fake_dhan_token(issued_at=now - timedelta(hours=23), expires_at=now + timedelta(minutes=20))
    regenerated_token = _fake_dhan_token(issued_at=now, expires_at=now + timedelta(days=1))

    db = SessionLocal()
    try:
        db.query(ServiceCredential).delete()
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_access_token", expired_token)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_pin", "4321")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_totp_secret", "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_token_renewal_lead_seconds", 3600)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_profile_check_seconds", 900)

    def fake_request_json(method: str, url: str, **kwargs):
        if url.endswith("/profile"):
            headers = kwargs.get("headers") or {}
            if headers.get("access-token") == regenerated_token:
                return {
                    "dhanClientId": "1103337749",
                    "tokenValidity": "15/03/2026 10:00",
                    "dataPlan": "Active",
                    "dataValidity": "2026-04-03 21:50:36.0",
                }
            raise DhanApiError("DHAN_PROFILE_FAILED", "token expired", auth_failed=True)
        if url.endswith("/generateAccessToken"):
            return {
                "accessToken": regenerated_token,
                "expiryTime": "2026-03-15T10:00:00.000",
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(dhan_credential_service, "_request_json", fake_request_json)

    dhan_credential_service.reset_runtime_state()
    dhan_credential_service.initialize(force_reload=True)

    assert dhan_credential_service.ensure_token_fresh() is True
    snapshot = dhan_credential_service.snapshot()
    assert snapshot.access_token == regenerated_token
    assert snapshot.token_source == "totp"

    db = SessionLocal()
    try:
        stored = db.query(ServiceCredential).filter(ServiceCredential.provider == "dhan").first()
        assert stored is not None
        assert stored.access_token == regenerated_token
        assert stored.token_source == "totp"
    finally:
        db.close()


def test_dhan_issue_lease_forces_profile_validation_before_handing_out_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_test_runtime()
    now = datetime.now(timezone.utc)
    access_token = _fake_dhan_token(issued_at=now, expires_at=now + timedelta(days=1))

    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_access_token", access_token)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_pin", "4321")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_totp_secret", "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_profile_check_seconds", 3600)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_token_renewal_lead_seconds", 3600)

    called_urls: list[str] = []

    def fake_request_json(method: str, url: str, **kwargs):
        called_urls.append(url)
        if url.endswith("/profile"):
            headers = kwargs.get("headers") or {}
            assert headers.get("access-token") == access_token
            return {
                "dhanClientId": "1103337749",
                "tokenValidity": (now + timedelta(days=1)).strftime("%d/%m/%Y %H:%M"),
                "dataPlan": "Active",
                "dataValidity": (now + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S.0"),
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(dhan_credential_service, "_request_json", fake_request_json)

    dhan_credential_service.reset_runtime_state()
    dhan_credential_service.initialize(force_reload=True)

    lease = dhan_credential_service.issue_lease()

    assert any(url.endswith("/profile") for url in called_urls)
    assert not any(url.endswith("/generateAccessToken") for url in called_urls)
    assert lease.access_token == access_token
    assert lease.last_profile_checked_at is not None
    assert lease.last_lease_issued_at is not None


def test_dhan_scheduler_fires_on_weekends() -> None:
    """Scheduler must fire daily, not just on trading days."""
    from services.dhan_credential_service import DhanCredentialService

    # Saturday 2026-03-21 at 04:00 UTC (after 03:20 target)
    saturday = datetime(2026, 3, 21, 4, 0, tzinfo=timezone.utc)
    next_run = DhanCredentialService._next_rotation_time(saturday)
    # Should be Sunday 03:20 UTC, not skip to Monday
    assert next_run.weekday() == 6  # Sunday
    assert next_run.hour == 3
    assert next_run.minute == 20

    # Sunday 2026-03-22 at 01:00 UTC (before 03:20 target)
    sunday_early = datetime(2026, 3, 22, 1, 0, tzinfo=timezone.utc)
    next_run = DhanCredentialService._next_rotation_time(sunday_early)
    # Should be today (Sunday) at 03:20 UTC
    assert next_run.day == 22
    assert next_run.hour == 3
    assert next_run.minute == 20


def test_market_provider_health_route_reports_runtime_state(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    now = datetime.now(timezone.utc)

    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_access_token", _fake_dhan_token(issued_at=now, expires_at=now + timedelta(days=1)))
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_pin", "4321")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_totp_secret", "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_p0_slack_webhook_url", "https://slack.example")

    dhan_credential_service.reset_runtime_state()
    dhan_credential_service.initialize(force_reload=True)
    market_data_service.reset_runtime_state_for_tests()
    market_data_service._health.last_option_chain_success_at = now
    market_data_service._health.last_feed_message_at = now
    market_data_service._health.last_market_data_at = now

    response = client.get("/api/v1/market/provider-health", headers=headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["provider"] == "dhan"
    assert payload["configured"] is True
    assert payload["p0_status"] == "ok"
    assert payload["slack_configured"] is True
    assert payload["totp_regeneration_enabled"] is True


def test_market_data_incident_alerts_only_on_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    sent: list[str] = []
    now = datetime.now(timezone.utc)

    monkeypatch.setattr(market_data_module.settings, "dhan_p0_slack_webhook_url", "https://slack.example")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_access_token", _fake_dhan_token(issued_at=now, expires_at=now + timedelta(days=1)))
    dhan_credential_service.reset_runtime_state()
    dhan_credential_service.initialize(force_reload=True)
    market_data_service.reset_runtime_state_for_tests()
    monkeypatch.setattr(
        market_data_service,
        "get_provider_health",
        lambda: SimpleNamespace(
            token_source="totp",
            token_expires_at=now + timedelta(days=1),
            last_token_refresh_at=now - timedelta(minutes=1),
            last_profile_check_at=now - timedelta(minutes=2),
            last_option_chain_success_at=now - timedelta(minutes=3),
            last_feed_message_at=now - timedelta(minutes=4),
        ),
    )

    async def fake_send_p0_slack_alert(*, title: str, lines: list[str]) -> bool:
        sent.append(title)
        return True

    monkeypatch.setattr(market_data_module, "send_p0_slack_alert", fake_send_p0_slack_alert)

    asyncio.run(market_data_service._open_incident("DHAN_AUTH_FAILED", "Token rejected by Dhan"))
    asyncio.run(market_data_service._open_incident("DHAN_AUTH_FAILED", "Token rejected by Dhan"))
    asyncio.run(market_data_service._close_incident("Token recovered"))

    assert sent == ["[P0] Dhan token failed", "[RECOVERY] Dhan token regenerated"]


def test_market_data_non_auth_incidents_do_not_page_slack(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    sent: list[str] = []
    now = datetime.now(timezone.utc)

    monkeypatch.setattr(market_data_module.settings, "dhan_p0_slack_webhook_url", "https://slack.example")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_access_token", _fake_dhan_token(issued_at=now, expires_at=now + timedelta(days=1)))
    dhan_credential_service.reset_runtime_state()
    dhan_credential_service.initialize(force_reload=True)
    market_data_service.reset_runtime_state_for_tests()

    async def fake_send_p0_slack_alert(*, title: str, lines: list[str]) -> bool:
        sent.append(title)
        return True

    monkeypatch.setattr(market_data_module, "send_p0_slack_alert", fake_send_p0_slack_alert)

    asyncio.run(market_data_service._open_incident("DHAN_RATE_LIMITED", "Too many requests"))
    asyncio.run(market_data_service._close_incident("Recovered"))

    assert sent == []


def test_internal_dhan_lease_route_requires_authority_key_and_returns_snapshot(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(dependencies_module.settings, "dhan_authority_shared_secret", "authority-secret")
    monkeypatch.setattr(
        dhan_credential_service,
        "issue_lease",
        lambda: DhanCredentialSnapshot(
            configured=True,
            client_id="1103337749",
            access_token="lease-token-1",
            expires_at=now + timedelta(hours=6),
            token_source="totp",
            last_refreshed_at=now - timedelta(minutes=2),
            last_profile_checked_at=now - timedelta(minutes=1),
            last_rest_success_at=now - timedelta(seconds=30),
            data_plan_status="ACTIVE",
            data_valid_until=now + timedelta(days=30),
            last_lease_issued_at=now,
            generation=7,
            totp_regeneration_enabled=True,
        ),
    )

    denied = client.get("/internal/dhan/lease")
    assert denied.status_code == 401, denied.text

    response = client.get("/internal/dhan/lease", headers={"X-Dhan-Authority-Key": "authority-secret"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["client_id"] == "1103337749"
    assert payload["access_token"] == "lease-token-1"
    assert payload["generation"] == 7
    assert payload["token_source"] == "totp"
    assert payload["data_plan_status"] == "ACTIVE"
    assert payload["data_valid_until"] is not None
    assert payload["validated_at"] is not None


def test_internal_dhan_consumer_state_route_persists_state_and_surfaces_in_provider_health(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(dependencies_module.settings, "dhan_authority_shared_secret", "authority-secret")
    monkeypatch.setattr(market_data_module.settings, "dhan_p0_slack_webhook_url", "https://slack.example")
    monkeypatch.setattr(
        dhan_credential_service,
        "snapshot",
        lambda: DhanCredentialSnapshot(
            configured=True,
            client_id="1103337749",
            access_token="lease-token-2",
            expires_at=now + timedelta(hours=8),
            token_source="renew",
            last_refreshed_at=now - timedelta(minutes=3),
            last_profile_checked_at=now - timedelta(minutes=2),
            last_rest_success_at=now - timedelta(seconds=45),
            data_plan_status="ACTIVE",
            data_valid_until=now + timedelta(days=20),
            last_lease_issued_at=now - timedelta(minutes=5),
            generation=11,
            totp_regeneration_enabled=True,
        ),
    )
    market_data_service.reset_runtime_state_for_tests()

    payload = {
        "consumer": "auto_trader.market_feed",
        "instance_id": "worker-1",
        "state": "unhealthy",
        "reason": "WEBSOCKET_STALE",
        "message": "market feed packets stopped",
        "observed_at": now.isoformat(),
        "generation": 11,
    }

    response = client.post(
        "/internal/dhan/consumer-state",
        headers={"X-Dhan-Authority-Key": "authority-secret"},
        json=payload,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}

    snapshot = dhan_incident_service.snapshot()
    assert snapshot.incident_open is True
    assert len(snapshot.consumer_states) == 1
    consumer_state = snapshot.consumer_states[0]
    assert consumer_state.consumer == "auto_trader.market_feed"
    assert consumer_state.instance_id == "worker-1"
    assert consumer_state.state == "unhealthy"
    assert consumer_state.reason == "WEBSOCKET_STALE"
    assert consumer_state.message == "market feed packets stopped"
    assert consumer_state.generation == 11

    admin_headers = _login(client, "admin@lite.trade", "lite-admin-123")
    health = client.get("/api/v1/market/provider-health", headers=admin_headers)
    assert health.status_code == 200, health.text
    body = health.json()
    assert any(
        item["consumer"] == "auto_trader.market_feed"
        and item["instance_id"] == "worker-1"
        and item["state"] == "unhealthy"
        and item["reason"] == "WEBSOCKET_STALE"
        for item in body["consumer_states"]
    )


def test_stale_consumer_state_expires_and_recovery_clears_incident_since(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_test_runtime()
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_access_token", _fake_dhan_token(issued_at=now, expires_at=now + timedelta(days=1)))
    dhan_credential_service.reset_runtime_state()
    dhan_credential_service.initialize(force_reload=True)
    monkeypatch.setattr(dhan_incident_service_module.settings, "option_chain_refresh_seconds", 60)
    monkeypatch.setattr(dhan_incident_service_module.settings, "dhan_rest_stale_seconds", 30)
    monkeypatch.setattr(dhan_incident_service_module.settings, "dhan_realtime_stale_seconds", 20)

    db = SessionLocal()
    try:
        db.add(
            DhanConsumerState(
                consumer="auto_trader.market_feed",
                instance_id="worker-1",
                state="unhealthy",
                reason="WEBSOCKET_STALE",
                message="market feed packets stopped",
                observed_at=now - timedelta(minutes=2),
                generation=11,
            )
        )
        db.commit()
    finally:
        db.close()

    snapshot = dhan_incident_service.snapshot()
    assert snapshot.incident_open is False
    assert snapshot.opened_at is None
    assert snapshot.consumer_states == []

    health = market_data_service.get_provider_health()
    assert health.incident_open is False
    assert health.incident_since is None
    assert health.affected_consumers == []

    sent: list[tuple[str, str]] = []

    def fake_alert_sender(*, state: str, incident_class: str, reason: str, message: str) -> bool:
        sent.append((state, incident_class))
        return True

    dhan_incident_service.set_provider_health(
        unhealthy=True,
        reason="DHAN_AUTH_FAILED",
        message="Token rejected by Dhan",
        alert_sender=fake_alert_sender,
    )
    opening = dhan_incident_service.snapshot()
    assert opening.incident_open is True
    assert opening.opened_at is not None

    dhan_incident_service.set_provider_health(
        unhealthy=False,
        reason=None,
        message=None,
        alert_sender=fake_alert_sender,
    )
    recovered = dhan_incident_service.snapshot()
    assert recovered.incident_open is False
    assert recovered.opened_at is None

    recovered_health = market_data_service.get_provider_health()
    assert recovered_health.incident_since is None
    assert sent == [("P0", "PROVIDER_UNHEALTHY"), ("RECOVERY", "PROVIDER_UNHEALTHY")]


def test_dhan_incident_dedupe_persists_and_provider_health_reports_runtime_fields(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    admin_headers = _login(client, "admin@lite.trade", "lite-admin-123")
    monkeypatch.setattr(market_data_module.settings, "dhan_p0_slack_webhook_url", "https://slack.example")
    monkeypatch.setattr(
        dhan_credential_service,
        "snapshot",
        lambda: DhanCredentialSnapshot(
            configured=True,
            client_id="1103337749",
            access_token="lease-token-3",
            expires_at=now + timedelta(hours=4),
            token_source="totp",
            last_refreshed_at=now - timedelta(minutes=10),
            last_profile_checked_at=now - timedelta(minutes=5),
            last_rest_success_at=now - timedelta(seconds=15),
            data_plan_status="ACTIVE",
            data_valid_until=now + timedelta(days=15),
            last_lease_issued_at=now - timedelta(minutes=20),
            generation=13,
            totp_regeneration_enabled=True,
        ),
    )
    market_data_service.reset_runtime_state_for_tests()

    sent: list[dict[str, str]] = []

    def fake_alert_sender(*, state: str, incident_class: str, reason: str, message: str) -> bool:
        sent.append(
            {
                "state": state,
                "incident_class": incident_class,
                "reason": reason,
                "message": message,
            }
        )
        return True

    dhan_incident_service.set_provider_health(
        unhealthy=True,
        reason="DHAN_AUTH_FAILED",
        message="Token rejected by Dhan",
        alert_sender=fake_alert_sender,
    )
    dhan_incident_service.set_provider_health(
        unhealthy=True,
        reason="DHAN_AUTH_FAILED",
        message="Token rejected by Dhan",
        alert_sender=fake_alert_sender,
    )

    assert len(sent) == 1
    assert sent[0]["state"] == "P0"
    assert sent[0]["incident_class"] == "PROVIDER_UNHEALTHY"

    health = client.get("/api/v1/market/provider-health", headers=admin_headers)
    assert health.status_code == 200, health.text
    body = health.json()
    assert body["configured"] is True
    assert body["authority_mode"] == "lite"
    assert body["p0_status"] == "critical"
    assert body["incident_open"] is True
    assert body["incident_class"] == "PROVIDER_UNHEALTHY"
    assert body["incident_reason"] == "DHAN_AUTH_FAILED"
    assert body["incident_fingerprint"] is not None
    assert body["last_lease_issued_at"] is not None
    assert body["slack_configured"] is True
    assert body["totp_regeneration_enabled"] is True

    fresh_service = DhanIncidentService()
    snapshot = fresh_service.snapshot()
    assert snapshot.incident_open is True
    assert snapshot.fingerprint == body["incident_fingerprint"]

    dhan_incident_service.set_provider_health(
        unhealthy=False,
        reason=None,
        message=None,
        alert_sender=fake_alert_sender,
    )
    assert len(sent) == 2
    assert sent[1]["state"] == "RECOVERY"

    recovered = client.get("/api/v1/market/provider-health", headers=admin_headers)
    assert recovered.status_code == 200, recovered.text
    recovered_body = recovered.json()
    assert recovered_body["p0_status"] == "ok"
    assert recovered_body["incident_open"] is False


def test_dhan_incident_service_suppresses_non_auth_slack_alerts() -> None:
    _reset_test_runtime()
    sent: list[dict[str, str]] = []

    def fake_alert_sender(*, state: str, incident_class: str, reason: str, message: str) -> bool:
        sent.append(
            {
                "state": state,
                "incident_class": incident_class,
                "reason": reason,
                "message": message,
            }
        )
        return True

    dhan_incident_service.set_provider_health(
        unhealthy=True,
        reason="DHAN_RATE_LIMITED",
        message="Too many requests",
        alert_sender=fake_alert_sender,
    )
    dhan_incident_service.set_provider_health(
        unhealthy=False,
        reason=None,
        message=None,
        alert_sender=fake_alert_sender,
    )

    assert sent == []


def test_apply_chain_payload_merges_greeks_without_overwriting_ltp(monkeypatch: pytest.MonkeyPatch) -> None:
    """REST chain refresh should update Greeks/IV but preserve WebSocket-sourced LTP/OI/bid/ask."""
    _reset_test_runtime()
    market_data_service.reset_runtime_state_for_tests()

    # Simulate WebSocket-updated quotes already in memory
    market_data_service.quotes = {
        "NIFTY_2026-03-26_24000_CE": {
            "symbol": "NIFTY_2026-03-26_24000_CE",
            "security_id": "12345",
            "strike": 24000,
            "option_type": "CE",
            "expiry": "2026-03-26",
            "ltp": 150.0,    # WebSocket live price
            "bid": 149.5,    # WebSocket live bid
            "ask": 150.5,    # WebSocket live ask
            "bid_qty": 100,
            "ask_qty": 200,
            "iv": 15.0,
            "oi": 50000.0,   # WebSocket live OI
            "oi_lakhs": 0.5,
            "volume": 1000.0,
            "delta": 0.5,
            "gamma": 0.01,
            "theta": -5.0,
            "vega": 10.0,
            "_live_updated_at": datetime.now(timezone.utc),
        },
    }
    market_data_service._security_id_to_symbol = {"12345": "NIFTY_2026-03-26_24000_CE"}

    # REST chain returns stale LTP but fresh Greeks
    chain = {
        "quotes": {
            "NIFTY_2026-03-26_24000_CE": {
                "symbol": "NIFTY_2026-03-26_24000_CE",
                "security_id": "12345",
                "strike": 24000,
                "option_type": "CE",
                "expiry": "2026-03-26",
                "ltp": 145.0,    # Stale REST LTP — should NOT overwrite
                "bid": 144.5,    # Stale REST bid — should NOT overwrite
                "ask": 145.5,    # Stale REST ask — should NOT overwrite
                "bid_qty": 80,
                "ask_qty": 150,
                "iv": 16.5,      # Fresh IV — SHOULD update
                "oi": 48000.0,   # Stale REST OI — should NOT overwrite
                "oi_lakhs": 0.48,
                "volume": 900.0,
                "delta": 0.55,   # Fresh delta — SHOULD update
                "gamma": 0.012,  # Fresh gamma — SHOULD update
                "theta": -5.5,   # Fresh theta — SHOULD update
                "vega": 10.5,    # Fresh vega — SHOULD update
            },
        },
        "rows": [{"strike": 24000, "is_atm": True, "call": {"symbol": "NIFTY_2026-03-26_24000_CE"}, "put": {"symbol": "NIFTY_2026-03-26_24000_PE"}}],
        "security_id_to_symbol": {"12345": "NIFTY_2026-03-26_24000_CE"},
        "total_call_oi": 50000.0,
        "total_put_oi": 50000.0,
    }

    market_data_service._apply_chain_payload(chain, expiry="2026-03-26", now=datetime.now(timezone.utc))

    quote = market_data_service.quotes["NIFTY_2026-03-26_24000_CE"]
    # WebSocket-sourced fields should be preserved
    assert quote["ltp"] == 150.0, f"LTP should stay at WebSocket value, got {quote['ltp']}"
    assert quote["bid"] == 149.5
    assert quote["ask"] == 150.5
    assert quote["oi"] == 50000.0
    assert quote["volume"] == 1000.0
    # Greeks/IV should be updated from REST
    assert quote["iv"] == 16.5
    assert quote["delta"] == 0.55
    assert quote["gamma"] == 0.012
    assert quote["theta"] == -5.5
    assert quote["vega"] == 10.5


def test_apply_chain_payload_replaces_stale_live_quote_fields_with_rest_values() -> None:
    _reset_test_runtime()
    market_data_service.reset_runtime_state_for_tests()
    stale_live_updated_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    market_data_service.quotes = {
        "NIFTY_2026-03-26_24000_CE": {
            "symbol": "NIFTY_2026-03-26_24000_CE",
            "security_id": "12345",
            "strike": 24000,
            "option_type": "CE",
            "expiry": "2026-03-26",
            "ltp": 150.0,
            "bid": 149.5,
            "ask": 150.5,
            "oi": 50000.0,
            "volume": 1000.0,
            "_live_updated_at": stale_live_updated_at,
        },
    }

    chain = {
        "quotes": {
            "NIFTY_2026-03-26_24000_CE": {
                "symbol": "NIFTY_2026-03-26_24000_CE",
                "security_id": "12345",
                "strike": 24000,
                "option_type": "CE",
                "expiry": "2026-03-26",
                "ltp": 145.0,
                "bid": 144.5,
                "ask": 145.5,
                "oi": 48000.0,
                "oi_lakhs": 0.48,
                "volume": 900.0,
                "iv": 16.5,
            },
        },
        "rows": [{"strike": 24000, "is_atm": True, "call": {"symbol": "NIFTY_2026-03-26_24000_CE"}, "put": {"symbol": "NIFTY_2026-03-26_24000_PE"}}],
        "security_id_to_symbol": {"12345": "NIFTY_2026-03-26_24000_CE"},
        "total_call_oi": 50000.0,
        "total_put_oi": 50000.0,
    }

    market_data_service._apply_chain_payload(chain, expiry="2026-03-26", now=datetime.now(timezone.utc))

    quote = market_data_service.quotes["NIFTY_2026-03-26_24000_CE"]
    assert quote["ltp"] == 145.0
    assert quote["bid"] == 144.5
    assert quote["ask"] == 145.5
    assert quote["oi"] == 48000.0
    assert quote["volume"] == 900.0


def test_open_feed_incident_clears_stale_live_quotes() -> None:
    _reset_test_runtime()
    market_data_service.reset_runtime_state_for_tests()
    market_data_service.quotes = {
        "NIFTY_2026-03-26_24000_CE": {
            "symbol": "NIFTY_2026-03-26_24000_CE",
            "security_id": "12345",
            "strike": 24000,
            "option_type": "CE",
            "expiry": "2026-03-26",
            "ltp": 150.0,
            "bid": 149.5,
            "ask": 150.5,
            "_live_updated_at": datetime.now(timezone.utc) - timedelta(minutes=2),
        },
    }

    asyncio.run(market_data_service._open_incident("REALTIME_FEED_STALE", "feed stale"))

    quote = market_data_service.quotes["NIFTY_2026-03-26_24000_CE"]
    assert quote["ltp"] is None
    assert quote["bid"] is None
    assert quote["ask"] is None


def test_apply_chain_payload_persists_option_registry() -> None:
    _reset_test_runtime()
    market_data_service.reset_runtime_state_for_tests()
    observed_at = datetime(2026, 3, 21, 4, 0, tzinfo=timezone.utc)

    chain = {
        "quotes": {
            "NIFTY_2026-03-26_24000_CE": {
                "symbol": "NIFTY_2026-03-26_24000_CE",
                "security_id": "12345",
                "strike": 24000,
                "option_type": "CE",
                "expiry": "2026-03-26",
                "ltp": 145.0,
            },
            "NIFTY_2026-03-26_24000_PE": {
                "symbol": "NIFTY_2026-03-26_24000_PE",
                "security_id": "12346",
                "strike": 24000,
                "option_type": "PE",
                "expiry": "2026-03-26",
                "ltp": 132.0,
            },
        },
        "rows": [{"strike": 24000, "is_atm": True, "call": {"symbol": "NIFTY_2026-03-26_24000_CE"}, "put": {"symbol": "NIFTY_2026-03-26_24000_PE"}}],
        "security_id_to_symbol": {
            "12345": "NIFTY_2026-03-26_24000_CE",
            "12346": "NIFTY_2026-03-26_24000_PE",
        },
        "total_call_oi": 50000.0,
        "total_put_oi": 52000.0,
    }

    market_data_service._apply_chain_payload(chain, expiry="2026-03-26", now=observed_at)

    with SessionLocal() as db:
        records = (
            db.query(DhanInstrumentRegistry)
            .order_by(DhanInstrumentRegistry.symbol.asc())
            .all()
        )

    assert [record.symbol for record in records] == [
        "NIFTY_2026-03-26_24000_CE",
        "NIFTY_2026-03-26_24000_PE",
    ]
    assert records[0].security_id == "12345"
    assert records[0].expiry == "2026-03-26"
    assert records[0].first_seen.replace(tzinfo=timezone.utc) == observed_at
    assert records[0].last_seen.replace(tzinfo=timezone.utc) == observed_at


def test_fetch_candles_daily_option_history_ends_cleanly_at_registry_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    symbol = "NIFTY_2026-03-24_23300_PE"
    observed_at = datetime(2026, 3, 21, 4, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        db.add(
            DhanInstrumentRegistry(
                symbol=symbol,
                security_id="62589",
                root_symbol="NIFTY",
                exchange_segment="NSE_FNO",
                instrument_type="OPTIDX",
                expiry="2026-03-24",
                strike=23300,
                option_type="PE",
                first_seen=observed_at,
                last_seen=observed_at,
            )
        )
        db.commit()

    first_page_payload = {
        "timestamp": [
            "2026-03-18T00:00:00+00:00",
            "2026-03-19T00:00:00+00:00",
        ],
        "open": [210.0, 220.0],
        "high": [215.0, 225.0],
        "low": [205.0, 215.0],
        "close": [212.0, 221.0],
        "volume": [1000, 1200],
    }

    call_count = {"n": 0}

    def fake_call(operation_name, fn, **kwargs):
        call_count["n"] += 1
        if call_count["n"] > 1:
            pytest.fail("history paging should stop at the registry boundary without hitting Dhan again")
        return first_page_payload

    monkeypatch.setattr(market_data_service, "_has_dhan", lambda: True)
    monkeypatch.setattr(dhan_credential_service, "call", fake_call)

    first_page = market_data_service._fetch_candles("D", symbol=symbol)
    boundary = first_page["candles"][0]["time"]
    second_page = market_data_service._fetch_candles("D", before=boundary, symbol=symbol)

    assert call_count["n"] == 1
    assert first_page["candles"]
    assert second_page["candles"] == []
    assert second_page["degraded"] is False
    assert second_page["has_more"] is False
    assert second_page["next_before"] is None


def test_candle_cache_hits_for_current_window_regardless_of_date_shift(monkeypatch: pytest.MonkeyPatch) -> None:
    """Current-window candle requests (before=None) should cache on (security_id, timeframe) only."""
    _reset_test_runtime()
    market_data_service.reset_runtime_state_for_tests()

    call_count = {"n": 0}
    def fake_call(op, fn, **kw):
        call_count["n"] += 1
        return {"open": [100], "high": [105], "low": [95], "close": [102], "volume": [1000], "timestamp": [1711400000]}

    monkeypatch.setattr("services.market_data.dhan_credential_service.call", fake_call)
    market_data_service._candle_cache.clear()

    # First call — should fetch both the daily window and the live-session overlay
    market_data_service._fetch_candles("D", before=None, symbol="NIFTY 50")
    assert call_count["n"] == 2

    # Second call immediately — both should hit cache
    market_data_service._fetch_candles("D", before=None, symbol="NIFTY 50")
    assert call_count["n"] == 2, f"Expected cache hit, but Dhan was called {call_count['n']} times"


# ── Pulse claim token flow ─────────────────────────────────────────


def test_pulse_setup_creates_key_and_claim_token(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    resp = client.post("/api/v1/agent/pulse/setup", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "claim_token" in data
    assert "apk_url" in data
    assert "key_prefix" in data
    assert len(data["claim_token"]) > 10
    assert len(data["key_prefix"]) > 0


def test_pulse_claim_exchanges_token_for_api_key(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    setup = client.post("/api/v1/agent/pulse/setup", headers=headers).json()

    resp = client.post("/api/v1/agent/pulse/claim", json={"token": setup["claim_token"]})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "api_key" in data
    assert data["api_key"].startswith("lite_")


def test_pulse_claimed_token_cannot_be_reused(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    setup = client.post("/api/v1/agent/pulse/setup", headers=headers).json()

    # First claim succeeds
    resp1 = client.post("/api/v1/agent/pulse/claim", json={"token": setup["claim_token"]})
    assert resp1.status_code == 200

    # Second claim fails
    resp2 = client.post("/api/v1/agent/pulse/claim", json={"token": setup["claim_token"]})
    assert resp2.status_code == 401


def test_pulse_expired_token_rejected(client: TestClient) -> None:
    from models import PulseClaimToken as PCT

    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    setup = client.post("/api/v1/agent/pulse/setup", headers=headers).json()

    # Manually expire the token in the DB
    db = SessionLocal()
    try:
        claim = db.query(PCT).filter(PCT.claimed.is_(False)).first()
        claim.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/agent/pulse/claim", json={"token": setup["claim_token"]})
    assert resp.status_code == 401


def test_pulse_disconnect_revokes_key(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    client.post("/api/v1/agent/pulse/setup", headers=headers)

    resp = client.delete("/api/v1/agent/pulse/setup", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Status should show disconnected
    status_resp = client.get("/api/v1/agent/pulse/status", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["connected"] is False


def test_pulse_status_connected_after_setup_disconnected_after_delete(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")

    # Before setup
    resp = client.get("/api/v1/agent/pulse/status", headers=headers)
    assert resp.json()["connected"] is False

    # After setup
    client.post("/api/v1/agent/pulse/setup", headers=headers)
    resp = client.get("/api/v1/agent/pulse/status", headers=headers)
    data = resp.json()
    assert data["connected"] is True
    assert data["key_prefix"] is not None

    # After disconnect
    client.delete("/api/v1/agent/pulse/setup", headers=headers)
    resp = client.get("/api/v1/agent/pulse/status", headers=headers)
    assert resp.json()["connected"] is False


def test_pulse_setup_twice_rotates_key_and_invalidates_old_token(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")

    setup1 = client.post("/api/v1/agent/pulse/setup", headers=headers).json()
    setup2 = client.post("/api/v1/agent/pulse/setup", headers=headers).json()

    # Old token should be invalidated
    resp = client.post("/api/v1/agent/pulse/claim", json={"token": setup1["claim_token"]})
    assert resp.status_code == 401

    # New token should work
    resp = client.post("/api/v1/agent/pulse/claim", json={"token": setup2["claim_token"]})
    assert resp.status_code == 200

    # Key prefix should have changed
    assert setup1["key_prefix"] != setup2["key_prefix"]


def test_pulse_claimed_api_key_matches_stored_hash(client: TestClient) -> None:
    from models import AgentApiKey
    from security import hash_secret as hs

    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    setup = client.post("/api/v1/agent/pulse/setup", headers=headers).json()
    claim = client.post("/api/v1/agent/pulse/claim", json={"token": setup["claim_token"]}).json()

    api_key_raw = claim["api_key"]

    # Verify the returned key hashes to match what's stored in AgentApiKey
    db = SessionLocal()
    try:
        key = db.query(AgentApiKey).filter(
            AgentApiKey.name == "lite-pulse",
            AgentApiKey.is_active.is_(True),
        ).first()
        assert key is not None
        assert key.key_hash == hs(api_key_raw)
    finally:
        db.close()


def test_webauthn_register_options_excludes_existing_credentials(client: TestClient) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "admin@lite.trade").first()
        assert user is not None
        credential_id = base64.urlsafe_b64encode(b"cred-1").decode().rstrip("=")
        db.add(
            WebAuthnCredential(
                user_id=user.id,
                credential_id=credential_id,
                public_key=base64.urlsafe_b64encode(b"pub-1").decode().rstrip("="),
                sign_count=1,
                transports=["internal"],
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post("/api/v1/auth/webauthn/register-options", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["options"]["excludeCredentials"]) == 1
    assert body["options"]["excludeCredentials"][0]["id"] == credential_id


def test_webauthn_register_updates_existing_credential(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    register_options = client.post("/api/v1/auth/webauthn/register-options", headers=headers)
    assert register_options.status_code == 200, register_options.text

    credential_id_bytes = b"cred-2"
    public_key_bytes = b"pub-2"
    monkeypatch.setattr(
        auth_router_module,
        "verify_registration_response",
        lambda **_: SimpleNamespace(
            credential_id=credential_id_bytes,
            credential_public_key=public_key_bytes,
            sign_count=7,
        ),
    )

    response = client.post(
        "/api/v1/auth/webauthn/register",
        headers=headers,
        json={"credential": {"response": {"transports": ["internal"]}}},
    )
    assert response.status_code == 200, response.text

    response = client.post("/api/v1/auth/webauthn/register-options", headers=headers)
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/v1/auth/webauthn/register",
        headers=headers,
        json={"credential": {"response": {"transports": ["hybrid"]}}},
    )
    assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        credential_id = base64.urlsafe_b64encode(credential_id_bytes).decode().rstrip("=")
        credentials = db.query(WebAuthnCredential).filter(WebAuthnCredential.credential_id == credential_id).all()
        assert len(credentials) == 1
        assert credentials[0].sign_count == 7
        assert credentials[0].transports == ["hybrid"]
    finally:
        db.close()


def test_webauthn_register_verification_failure_returns_400_and_logs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    response = client.post("/api/v1/auth/webauthn/register-options", headers=headers)
    assert response.status_code == 200, response.text

    def _fail_verify(**_: object) -> None:
        raise ValueError("bad attestation")

    monkeypatch.setattr(auth_router_module, "verify_registration_response", _fail_verify)

    with caplog.at_level("WARNING", logger="lite.auth"):
        response = client.post(
            "/api/v1/auth/webauthn/register",
            headers=headers,
            json={"credential": {"response": {"transports": ["internal"]}}},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Passkey verification failed"
    assert "WebAuthn registration verification failed" in caplog.text


def test_webauthn_authentication_verification_failure_returns_401_and_logs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "admin@lite.trade").first()
        assert user is not None
        db.add(
            WebAuthnCredential(
                user_id=user.id,
                credential_id=base64.urlsafe_b64encode(b"cred-3").decode().rstrip("="),
                public_key=base64.urlsafe_b64encode(b"pub-3").decode().rstrip("="),
                sign_count=1,
                transports=["internal"],
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post("/api/v1/auth/webauthn/authenticate-options", json={"email": "admin@lite.trade"})
    assert response.status_code == 200, response.text

    def _fail_verify(**_: object) -> None:
        raise ValueError("bad signature")

    monkeypatch.setattr(auth_router_module, "verify_authentication_response", _fail_verify)

    with caplog.at_level("WARNING", logger="lite.auth"):
        response = client.post(
            "/api/v1/auth/webauthn/authenticate",
            json={
                "email": "admin@lite.trade",
                "credential": {
                    "rawId": base64.urlsafe_b64encode(b"cred-3").decode().rstrip("="),
                    "response": {},
                },
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication failed"
    assert "WebAuthn authentication verification failed" in caplog.text


def test_webauthn_client_error_logs_to_server(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING", logger="lite.auth"):
        response = client.post(
            "/api/v1/auth/webauthn/client-error",
            json={
                "stage": "register",
                "email": "admin@lite.trade",
                "code": "NotAllowedError",
                "message": "Fingerprint prompt was dismissed.",
            },
        )

    assert response.status_code == 204
    assert "WebAuthn client error stage=register" in caplog.text
