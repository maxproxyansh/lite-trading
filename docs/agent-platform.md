# Agent Platform

Lite now exposes a first-class agent surface designed for autonomous paper-trading workflows. Agents can self-onboard, discover their scoped portfolio, place and cancel orders, monitor positions and funds, square off positions, and ingest signals without a human manually creating API keys.

## Surfaces

- Native agent REST API under `/api/v1/agent/*`
- Dhan-compatible REST API under `/api/v1/agent/dhan/*`
- Python SDK in `/Users/proxy/trading/lite/backend/agent_sdk.py`
- CLI in `/Users/proxy/trading/lite/backend/scripts/lite_agent.py`

## Self-service onboarding

### Existing Lite account

Use `POST /api/v1/agent/bootstrap` with account credentials plus an agent name. Lite authenticates the account, ensures the `agent` portfolio exists, rotates any active key with the same agent name by default, and returns a new scoped API key.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/bootstrap \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "admin@lite.trade",
    "password": "lite-admin-123",
    "agent_name": "night-desk",
    "portfolio_kind": "agent"
  }'
```

### New account

If public signup is enabled, `POST /api/v1/agent/signup` creates the Lite account and immediately issues a scoped API key in the same response.

## Native agent API

These routes use `X-API-Key: <secret>`.

- `GET /api/v1/agent/me`
- `GET /api/v1/agent/orders`
- `GET /api/v1/agent/orders/{order_id}`
- `POST /api/v1/agent/orders`
- `POST /api/v1/agent/orders/{order_id}/cancel`
- `GET /api/v1/agent/positions`
- `POST /api/v1/agent/positions/{position_id}/square-off`
- `POST /api/v1/agent/positions/square-off`
- `GET /api/v1/agent/funds`
- `GET /api/v1/agent/signals/latest`
- `POST /api/v1/agent/signals`

Native order writes require `idempotency_key`.

## Dhan-compatible API

These aliases map back to the same Lite execution engine but use a Dhan-like request or response shape.

- `GET /api/v1/agent/dhan/orders`
- `GET /api/v1/agent/dhan/orders/{order_id}`
- `POST /api/v1/agent/dhan/orders`
- `DELETE /api/v1/agent/dhan/orders/{order_id}`
- `GET /api/v1/agent/dhan/positions`
- `POST /api/v1/agent/dhan/positions/{position_id}/exit`
- `GET /api/v1/agent/dhan/fundlimit`

For Dhan-style orders:

- use `correlationId` for idempotency
- use `quantity` in units, not lots
- `quantity` must be a multiple of the configured NIFTY lot size
- provide either `trading_symbol`, `security_id`, or `expiry + strike + option_type`

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/dhan/orders \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $LITE_AGENT_API_KEY" \
  -d '{
    "transaction_type": "BUY",
    "trading_symbol": "NIFTY_2026-03-12_22500_CE",
    "quantity": 65,
    "order_type": "MARKET",
    "product_type": "NRML",
    "correlationId": "night-desk-001"
  }'
```

## CLI

Bootstrap and persist credentials locally:

```bash
python3 /Users/proxy/trading/lite/backend/scripts/lite_agent.py \
  --base-url http://127.0.0.1:8000 \
  bootstrap \
  --email admin@lite.trade \
  --password lite-admin-123 \
  --agent-name night-desk
```

Inspect funds and positions:

```bash
python3 /Users/proxy/trading/lite/backend/scripts/lite_agent.py funds --pretty
python3 /Users/proxy/trading/lite/backend/scripts/lite_agent.py positions --pretty
```

Place a Dhan-compatible order:

```bash
python3 /Users/proxy/trading/lite/backend/scripts/lite_agent.py orders place \
  --side BUY \
  --trading-symbol NIFTY_2026-03-12_22500_CE \
  --quantity 65 \
  --order-type MARKET \
  --correlation-id cli-order-001
```

Square off all positions:

```bash
python3 /Users/proxy/trading/lite/backend/scripts/lite_agent.py square-off --all --pretty
```

The CLI stores the API key at `~/.config/lite-agent/config.json` by default and sets file permissions to `0600` when possible.

## SDK

```python
from agent_sdk import LiteAgentClient

client = LiteAgentClient(base_url="http://127.0.0.1:8000")
bootstrap = client.bootstrap(
    email="admin@lite.trade",
    password="lite-admin-123",
    agent_name="strategy-runner",
)

profile = client.profile()
funds = client.funds()
positions = client.positions()
order = client.dhan_order(
    {
        "transaction_type": "BUY",
        "trading_symbol": "NIFTY_2026-03-12_22500_CE",
        "quantity": 65,
        "order_type": "MARKET",
        "product_type": "NRML",
        "correlationId": "sdk-order-001",
    }
)
```

## Security, privacy, and performance

- Every API key is bound to one user-owned portfolio.
- Keys can be rotated automatically by reusing the same `agent_name`.
- Keys now carry `expires_at`, `revoked_at`, and `last_used_at`.
- Bootstrap and signup responses are returned with `Cache-Control: no-store`.
- Agent requests cannot cross portfolio boundaries, even if the payload includes another portfolio ID.
- Dhan-compatible writes still enforce idempotency through `correlationId`.
- WebSocket and HTTP agent auth both reject expired or revoked keys.
- Key `last_used_at` writes are throttled to avoid a database commit on every request.
- Existing order processing still uses row locking and the unique idempotency index for safe concurrent execution.

## Human operator controls

The signed-in user can manage their own keys through:

- `GET /api/v1/auth/api-keys`
- `POST /api/v1/auth/api-keys`
- `DELETE /api/v1/auth/api-keys/{key_id}`

These routes let humans inspect or revoke agent credentials without sharing broad account access.
