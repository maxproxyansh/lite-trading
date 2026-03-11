# Agent Platform

Lite exposes an agent-first trading surface for autonomous paper-trading workflows. An agent can sign up or bootstrap itself, fetch market data, place and cancel orders, monitor positions and funds, square off risk, and listen to live updates over WebSocket with no human-created API key step.

Base URL used in all examples:

```text
https://lite-options-api-production.up.railway.app
```

## Discovery

An agent does not need to reverse-engineer the frontend to discover the API.

- `GET /` returns health plus links to the API meta, docs, and OpenAPI endpoints
- `GET /api/v1/meta` returns the machine-readable discovery contract
- `GET /api/v1/docs` serves Swagger UI
- `GET /api/v1/openapi.json` serves the OpenAPI schema
- `GET /api/v1/redoc` serves ReDoc

Friendly public aliases on the frontend domain:

- `https://litetrade.vercel.app/api/meta`
- `https://litetrade.vercel.app/api/docs`
- `https://litetrade.vercel.app/api/openapi.json`
- `https://litetrade.vercel.app/api/redoc`

Start here:

```bash
curl https://lite-options-api-production.up.railway.app/api/v1/meta
```

The response includes:

- `docs_url`
- `openapi_url`
- `redoc_url`
- `websocket.url`
- auth expectations for human JWT vs agent API keys
- PCR calculation semantics
- absolute URLs for the major agent and market routes

## Quickstart

### Zero to first trade

1. Sign up and get an API key
2. Read the live market snapshot
3. Read the option chain for the active expiry
4. Place an order
5. Check the resulting position and funds

### 1. Sign up

If public signup is enabled:

```bash
curl -X POST https://lite-options-api-production.up.railway.app/api/v1/agent/signup \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "your-email@example.com",
    "display_name": "Your Agent",
    "password": "your-password",
    "agent_name": "strategy-runner",
    "portfolio_kind": "agent"
  }'
```

If you already have a Lite account, use bootstrap instead:

```bash
curl -X POST https://lite-options-api-production.up.railway.app/api/v1/agent/bootstrap \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "your-email@example.com",
    "password": "your-password",
    "agent_name": "strategy-runner",
    "portfolio_kind": "agent"
  }'
```

Save the returned `api_key` as `LITE_AGENT_API_KEY`.

The returned payload also includes:

- `agent.expires_at` so the agent can see when the key expires
- `links.meta`, `links.docs`, `links.openapi`, and `links.websocket` for self-discovery

Use the returned `api_key` for autonomous agent workflows. The human JWT login token is for browser or human-session auth and expires much faster.

### 2. Check the market snapshot

```bash
curl https://lite-options-api-production.up.railway.app/api/v1/market/snapshot \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

You will receive the current NIFTY spot price, day change, market status, and available expiries.

### 3. Read the option chain

```bash
curl "https://lite-options-api-production.up.railway.app/api/v1/market/chain" \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

To target a specific expiry:

```bash
curl "https://lite-options-api-production.up.railway.app/api/v1/market/chain?expiry=2026-03-12" \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

### 4. Place a trade

Native Lite order:

```bash
curl -X POST https://lite-options-api-production.up.railway.app/api/v1/agent/orders \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $LITE_AGENT_API_KEY" \
  -d '{
    "portfolio_id": "agent-portfolio-id-from-signup",
    "symbol": "NIFTY_2026-03-12_22500_CE",
    "expiry": "2026-03-12",
    "strike": 22500,
    "option_type": "CE",
    "side": "BUY",
    "order_type": "MARKET",
    "product": "NRML",
    "validity": "DAY",
    "lots": 1,
    "idempotency_key": "quickstart-001"
  }'
```

Dhan-compatible order:

```bash
curl -X POST https://lite-options-api-production.up.railway.app/api/v1/agent/dhan/orders \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $LITE_AGENT_API_KEY" \
  -d '{
    "transaction_type": "BUY",
    "trading_symbol": "NIFTY_2026-03-12_22500_CE",
    "quantity": 65,
    "order_type": "MARKET",
    "product_type": "NRML",
    "correlationId": "quickstart-001"
  }'
```

### 5. Verify positions and funds

```bash
curl https://lite-options-api-production.up.railway.app/api/v1/agent/positions \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

```bash
curl https://lite-options-api-production.up.railway.app/api/v1/agent/funds \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

## Authentication Model

- Human session auth uses JWT plus cookies on `/api/v1/auth/*`
- Agent auth uses `X-API-Key` on `/api/v1/agent/*`, `/api/v1/agent/dhan/*`, `/api/v1/market/*`, and the WebSocket
- Human JWT access tokens are short-lived by design. The default expiry is 15 minutes.
- Agent API keys are the recommended auth mode for autonomous agents. The default expiry is 30 days unless `expires_in_days` overrides it.
- Agent keys are portfolio-scoped, expiring, revocable, and rotatable
- Reusing the same `agent_name` on bootstrap rotates the prior active key by default

## Market Data API

Agents can read market data directly with their API key.

### `GET /api/v1/market/snapshot`

Returns the top-level NIFTY market snapshot.

```bash
curl https://lite-options-api-production.up.railway.app/api/v1/market/snapshot \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

Sample response:

```json
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
  "degraded": false,
  "degraded_reason": null,
  "updated_at": "2026-03-11T09:20:00Z"
}
```

### `GET /api/v1/market/chain`

Returns the option chain for the active expiry or a specific expiry.

```bash
curl "https://lite-options-api-production.up.railway.app/api/v1/market/chain?expiry=2026-03-12" \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

The response includes strike rows, LTP, bid/ask, IV, OI, and Greeks for both CE and PE legs.

PCR note:

- `pcr` is calculated as `put_oi_total / call_oi_total`
- `pcr_scope=all_loaded_strikes_for_active_expiry` means it uses all currently loaded strikes for the active expiry, not only ATM or near-ATM strikes
- use `call_oi_total` and `put_oi_total` if you want to verify the ratio directly

### `GET /api/v1/market/expiries`

Returns available expiries and the currently active expiry.

```bash
curl https://lite-options-api-production.up.railway.app/api/v1/market/expiries \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

### `GET /api/v1/market/candles`

Returns OHLC candle data. Supported timeframes are broker-data dependent; common values include `1m`, `5m`, `15m`, `1h`, `D`, `W`, and `M`.
By default this returns the NIFTY spot chart. Pass `symbol` or `security_id` to fetch a specific option contract instead.

```bash
curl "https://lite-options-api-production.up.railway.app/api/v1/market/candles?timeframe=15m" \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

```bash
curl "https://lite-options-api-production.up.railway.app/api/v1/market/candles?timeframe=5m&symbol=NIFTY_2026-03-12_22500_CE" \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

### `GET /api/v1/market/depth/{symbol}`

Returns the current bid/ask depth for a symbol.

```bash
curl https://lite-options-api-production.up.railway.app/api/v1/market/depth/NIFTY_2026-03-12_22500_CE \
  -H "X-API-Key: $LITE_AGENT_API_KEY"
```

## Native Agent API

These routes use `X-API-Key: <secret>`.

- `GET /api/v1/agent/me`
- `GET /api/v1/agent/orders`
- `GET /api/v1/agent/orders/{order_id}`
- `GET /api/v1/agent/orders/{order_id}/linked`
- `POST /api/v1/agent/orders`
- `POST /api/v1/agent/orders/bracket`
- `PATCH /api/v1/agent/orders/{order_id}`
- `POST /api/v1/agent/orders/{order_id}/cancel`
- `GET /api/v1/agent/positions`
- `POST /api/v1/agent/positions/{position_id}/close`
- `POST /api/v1/agent/positions/{position_id}/square-off`
- `POST /api/v1/agent/positions/square-off`
- `GET /api/v1/agent/funds`
- `GET /api/v1/agent/alerts`
- `POST /api/v1/agent/alerts`
- `DELETE /api/v1/agent/alerts/{alert_id}`
- `GET /api/v1/agent/webhooks`
- `POST /api/v1/agent/webhooks`
- `DELETE /api/v1/agent/webhooks/{webhook_id}`
- `GET /api/v1/agent/analytics/detailed`
- `GET /api/v1/agent/signals/latest`
- `POST /api/v1/agent/signals`

Native writes require `idempotency_key`.

Order `source` semantics:

- `source="agent"` means the order was submitted through the agent API key surface
- `source="human"` means it came through the human JWT/session surface
- `source` describes the submission channel, not the portfolio kind

## Dhan-Compatible Agent API

These routes map to the same Lite execution engine but use Dhan-like request or response shapes.

- `GET /api/v1/agent/dhan/orders`
- `GET /api/v1/agent/dhan/orders/{order_id}`
- `POST /api/v1/agent/dhan/orders`
- `DELETE /api/v1/agent/dhan/orders/{order_id}`
- `GET /api/v1/agent/dhan/positions`
- `POST /api/v1/agent/dhan/positions/{position_id}/exit`
- `GET /api/v1/agent/dhan/fundlimit`

Rules:

- use `correlationId` for idempotency
- use `quantity` in units, not lots
- quantity must be a multiple of the configured lot size
- provide `trading_symbol`, `security_id`, or `expiry + strike + option_type`

## WebSocket

Endpoint:

```text
wss://lite-options-api-production.up.railway.app/api/v1/ws
```

Authenticate with `X-API-Key`.

### Python example

```python
import asyncio
import json

import websockets


async def main() -> None:
    async with websockets.connect(
        "wss://lite-options-api-production.up.railway.app/api/v1/ws",
        extra_headers={"X-API-Key": "your-agent-api-key"},
    ) as ws:
        while True:
            message = await ws.recv()
            event = json.loads(message)
            print(event["type"], event["payload"])


asyncio.run(main())
```

Current event types:

- `market.snapshot`
- `option.chain`
- `option.quotes`
- `portfolio.refresh`
- `signal.updated`

Notes:

- send `ping` to receive `pong`
- agents should reconnect on disconnect and then reconcile state using `/api/v1/agent/me`, `/api/v1/agent/orders`, `/api/v1/agent/positions`, and `/api/v1/agent/funds`

## SDK

Python SDK location:

```text
backend/agent_sdk.py
```

Key methods:

- `bootstrap(...)`
- `signup(...)`
- `profile()`
- `bracket_order(payload)`
- `snapshot()`
- `expiries()`
- `chain(expiry=None)`
- `candles(timeframe="15m")`
- `depth(symbol)`
- `alerts()`
- `create_alert(...)`
- `delete_alert(alert_id)`
- `funds()`
- `positions()`
- `orders()`
- `order(payload)`
- `linked_orders(order_id)`
- `detailed_analytics(...)`
- `dhan_order(payload)`
- `webhooks()`
- `create_webhook(url, events)`
- `delete_webhook(webhook_id)`
- `square_off(position_id)`
- `square_off_all()`

Example:

```python
from agent_sdk import LiteAgentClient

client = LiteAgentClient(
    base_url="https://lite-options-api-production.up.railway.app",
    api_key="your-agent-api-key",
)

snapshot = client.snapshot()
chain = client.chain()
positions = client.positions()
funds = client.funds()
```

## CLI

CLI location:

```text
backend/scripts/lite_agent.py
```

Examples:

```bash
python3 backend/scripts/lite_agent.py --base-url https://lite-options-api-production.up.railway.app market snapshot --pretty
python3 backend/scripts/lite_agent.py --base-url https://lite-options-api-production.up.railway.app market chain --pretty
python3 backend/scripts/lite_agent.py --base-url https://lite-options-api-production.up.railway.app market candles --timeframe 1h --pretty
python3 backend/scripts/lite_agent.py --base-url https://lite-options-api-production.up.railway.app positions --pretty
python3 backend/scripts/lite_agent.py --base-url https://lite-options-api-production.up.railway.app square-off --all --pretty
```

The CLI stores credentials at `~/.config/lite-agent/config.json` by default and attempts to apply `0600` permissions.

## Error Reference

| Status | Meaning | Typical cause |
| --- | --- | --- |
| `401` | Invalid or expired auth | Missing or expired API key, missing session token |
| `403` | Access denied | Wrong portfolio, missing scope |
| `404` | Resource not found | Order, position, or portfolio does not exist |
| `409` | Conflict | Duplicate idempotency key or active key name collision when rotation is disabled |
| `422` | Validation error | Bad quantity, missing field, invalid order parameters |
| `429` | Rate limit exceeded | Too many requests in the configured window |
| `503` | Upstream or market data unavailable | Dhan not configured, quote lookup unavailable |

## Security and Privacy Notes

- Every agent key is bound to a single user-owned portfolio
- Keys support expiry, revocation, and automatic rotation
- Bootstrap and signup responses are returned with `Cache-Control: no-store`
- Agent requests cannot read or trade another user’s portfolio
- WebSocket and HTTP auth both reject expired or revoked keys
- Dhan-compatible writes still enforce idempotency through `correlationId`
