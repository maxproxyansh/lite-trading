from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import uuid
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
os.environ["ALLOW_PUBLIC_SIGNUP"] = "false"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@lite.trade"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "lite-admin-123"
os.environ["BOOTSTRAP_ADMIN_NAME"] = "Lite Admin"
os.environ["BOOTSTRAP_AGENT_KEY"] = "lite-agent-dev-key"
os.environ["BOOTSTRAP_AGENT_NAME"] = "bootstrap-agent"

from database import Base, SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from routers.websocket import broadcast_message  # noqa: E402
from services.auth_service import ensure_bootstrap_state  # noqa: E402
from services.market_data import market_data_service  # noqa: E402
from services.signal_adapter import signal_adapter  # noqa: E402


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


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
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

    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "blocked@example.com", "display_name": "Blocked", "password": "blocked-pass-1"},
    )
    assert signup.status_code == 403
    assert signup.json()["detail"] == "Public signup is disabled"


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

    headers = _login(client, "admin@lite.trade", "lite-admin-123")
    token = headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/api/v1/ws?token={token}") as websocket:
        asyncio.run(broadcast_message("market.snapshot", {"spot": 22510}))
        message = websocket.receive_json()
        assert message["type"] == "market.snapshot"
        assert message["payload"]["spot"] == 22510
