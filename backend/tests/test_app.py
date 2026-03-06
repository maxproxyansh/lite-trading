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

from database import Base, SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from models import AgentApiKey  # noqa: E402
from routers.websocket import broadcast_message  # noqa: E402
from security import hash_secret  # noqa: E402
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


def _login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "admin@lite.trade", "password": "lite-admin-123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


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
    with TestClient(app) as client:
        yield client


def test_auth_and_trading_flow(client: TestClient) -> None:
    headers = _login(client)

    portfolios = client.get("/api/v1/portfolios", headers=headers)
    assert portfolios.status_code == 200
    assert {item["id"] for item in portfolios.json()} == {"manual", "agent"}

    order = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "portfolio_id": "manual",
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
    assert order.status_code == 200
    assert order.json()["status"] == "FILLED"

    positions = client.get("/api/v1/positions?portfolio_id=manual", headers=headers)
    assert positions.status_code == 200
    assert len(positions.json()) == 1
    assert positions.json()[0]["net_quantity"] == 25

    funds = client.get("/api/v1/funds?portfolio_id=manual", headers=headers)
    assert funds.status_code == 200
    assert funds.json()["available_funds"] < 500000

    analytics = client.get("/api/v1/analytics?portfolio_id=manual", headers=headers)
    assert analytics.status_code == 200
    assert analytics.json()["filled_orders"] == 1


def test_agent_scope_enforcement(client: TestClient) -> None:
    secret = "lite_scope_test_key"
    db = SessionLocal()
    try:
        db.add(
            AgentApiKey(
                name="signals-only",
                key_prefix=secret[:12],
                key_hash=hash_secret(secret),
                scopes=["signals:read"],
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/agent/orders",
        headers={"X-API-Key": secret},
        json={
            "portfolio_id": "agent",
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
    assert response.status_code == 403


def test_signal_adapter_ingests_latest_json(client: TestClient) -> None:
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
        "target": 138,
        "stop_loss": 96,
    }
    (SIGNAL_ROOT / "latest_signal.json").write_text(json.dumps(payload))

    asyncio.run(signal_adapter.ingest_once())
    headers = _login(client)
    response = client.get("/api/v1/signals/latest", headers=headers)
    assert response.status_code == 200
    assert response.json()["option_type"] == "CE"
    assert response.json()["confidence_label"] == "HIGH"
    assert response.json()["is_actionable"] is True


def test_websocket_requires_auth_and_streams_events(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.receive_text()
    assert exc.value.code == 4401

    headers = _login(client)
    token = headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/api/v1/ws?token={token}") as websocket:
        asyncio.run(broadcast_message("market.snapshot", {"spot": 22510}))
        message = websocket.receive_json()
        assert message["type"] == "market.snapshot"
        assert message["payload"]["spot"] == 22510
