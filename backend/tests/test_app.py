from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


TEST_ROOT = Path(tempfile.gettempdir()) / f"lite-backend-tests-{uuid.uuid4().hex}"
SIGNAL_ROOT = TEST_ROOT / "signals"
SIGNAL_ROOT.mkdir(parents=True, exist_ok=True)
(SIGNAL_ROOT / "logs").mkdir(parents=True, exist_ok=True)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

os.environ["LITE_DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'lite-test.db'}"
os.environ["SIGNAL_ROOT"] = str(SIGNAL_ROOT)
os.environ["DHAN_CLIENT_ID"] = ""
os.environ["DHAN_ACCESS_TOKEN"] = ""
os.environ["ALLOW_PUBLIC_SIGNUP"] = "true"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@lite.trade"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "lite-admin-123"
os.environ["BOOTSTRAP_ADMIN_NAME"] = "Lite Admin"
os.environ["BOOTSTRAP_AGENT_KEY"] = "lite-agent-dev-key"
os.environ["BOOTSTRAP_AGENT_NAME"] = "bootstrap-agent"

from database import Base, SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from rate_limit import _rate_buckets  # noqa: E402
from routers.websocket import broadcast_message  # noqa: E402
from services.alert_service import sync_alerts  # noqa: E402
from services.auth_service import ensure_bootstrap_state  # noqa: E402
from services.market_data import market_data_service  # noqa: E402
from services.signal_adapter import signal_adapter  # noqa: E402
from services.trading_service import process_open_orders_sync  # noqa: E402


def _seed_market() -> None:
    market_data_service.snapshot.update(
        {
            "spot_symbol": "NIFTY 50",
            "spot": 22450.0,
            "change": 120.5,
            "change_pct": 0.54,
            "vix": 14.2,
            "pcr": 0.96,
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
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _rate_buckets.clear()
    db = SessionLocal()
    try:
        ensure_bootstrap_state(db)
    finally:
        db.close()
    _seed_market()
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
    assert len(agent_orders.json()) == 1

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

    expiries = client.get("/api/v1/market/expiries", headers={"X-API-Key": api_key})
    assert expiries.status_code == 200, expiries.text
    assert "expiries" in expiries.json()

    chain = client.get("/api/v1/market/chain", headers={"X-API-Key": api_key})
    assert chain.status_code == 200, chain.text
    assert chain.json()["snapshot"]["active_expiry"] == "2026-03-12"

    candles = client.get("/api/v1/market/candles?timeframe=15m", headers={"X-API-Key": api_key})
    assert candles.status_code == 200, candles.text
    assert candles.json()["timeframe"] == "15m"

    depth = client.get("/api/v1/market/depth/NIFTY_2026-03-12_22500_CE", headers={"X-API-Key": api_key})
    assert depth.status_code == 200, depth.text
    assert depth.json()["symbol"] == "NIFTY_2026-03-12_22500_CE"


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


def test_unauthenticated_market_access_rejected(client: TestClient) -> None:
    for path in ["/api/v1/market/snapshot", "/api/v1/market/expiries", "/api/v1/market/chain", "/api/v1/market/candles", "/api/v1/market/depth/NIFTY"]:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} should reject unauthenticated requests, got {resp.status_code}"


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
        assert sync_alerts(db) == 1
    finally:
        db.close()

    admin_alerts = client.get("/api/v1/alerts", headers=admin_headers)
    assert admin_alerts.status_code == 200, admin_alerts.text
    payload = admin_alerts.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "TRIGGERED"

    deleted = client.delete(f"/api/v1/alerts/{alert_id}", headers=admin_headers)
    assert deleted.status_code == 204, deleted.text
    after_delete = client.get("/api/v1/alerts", headers=admin_headers)
    assert after_delete.status_code == 200, after_delete.text
    assert after_delete.json() == []


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
    with client.websocket_connect("/api/v1/ws") as websocket:
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
    monkeypatch.setattr(market_data_service, "_client", lambda: fake_client)

    response = market_data_service._fetch_candles("15m")

    assert len(response["candles"]) == 600
    assert response["candles"][0]["time"] == timestamps[0]
    assert response["candles"][-1]["time"] == timestamps[-1]
    assert response["has_more"] is True
    assert response["next_before"] == timestamps[0]
    assert fake_client.last_kwargs["interval"] == 15


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
    monkeypatch.setattr(market_data_service, "_client", lambda: FakeDhanClient())

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
    monkeypatch.setattr(market_data_service, "_client", lambda: fake_client)
    monkeypatch.setattr(
        market_data_service,
        "_fetch_option_chain",
        lambda expiry: {
            "quotes": {
                symbol: {
                    "symbol": symbol,
                    "security_id": "778899",
                    "strike": 22450,
                    "option_type": "PE",
                    "expiry": expiry,
                    "ltp": 86.5,
                }
            }
        },
    )

    response = market_data_service._fetch_candles("15m", symbol=symbol)

    assert [candle["time"] for candle in response["candles"]] == timestamps
    assert fake_client.last_kwargs["security_id"] == "778899"
    assert fake_client.last_kwargs["exchange_segment"] == "NSE_FNO"
    assert fake_client.last_kwargs["instrument_type"] == "OPTIDX"


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
    monkeypatch.setattr(market_data_service, "_client", lambda: fake_client)
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
    assert response.json()["detail"] == "Unsupported symbol format. Expected NIFTY 50 or NIFTY_YYYY-MM-DD_STRIKE_CE|PE"
