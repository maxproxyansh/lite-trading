# Lite Options Terminal

Lite is a private, options-only paper-trading terminal built to feel broker-grade rather than demo-grade. The app is split into:

- `frontend`: React + Vite + Tailwind terminal UI.
- `backend`: FastAPI API with auth, portfolios, orders, positions, funds, analytics, signal ingestion, and Dhan-backed market data polling.

## Local development

1. Copy `backend/.env.example` to `backend/.env` and fill in Dhan credentials if you want live market data.
2. Start the backend:

   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

3. Start the frontend:

   ```bash
   cd frontend
   npm install
   npm run sync:api
   npm run dev
   ```

4. Provision the first operator account:

   Set these in `backend/.env` before starting the backend:

   - `BOOTSTRAP_ADMIN_EMAIL`
   - `BOOTSTRAP_ADMIN_PASSWORD`
   - `BOOTSTRAP_ADMIN_NAME`
   - `BOOTSTRAP_AGENT_KEY`

   The backend will create the admin user plus two owned portfolios:

   - `manual`
   - `agent`

5. Sign in with the bootstrap admin credentials you configured.

## Key endpoints

- Human auth: `/api/v1/auth/*`
- Trading: `/api/v1/orders`, `/api/v1/positions`, `/api/v1/funds`, `/api/v1/analytics`
- Market data: `/api/v1/market/*`
- Alerts: `/api/v1/alerts`
- Signals: `/api/v1/signals`
- Agent API: `/api/v1/agent/*`
- Agent bootstrap: `/api/v1/agent/bootstrap`, `/api/v1/agent/signup`
- Dhan-compatible agent API: `/api/v1/agent/dhan/*`
- WebSocket: `/api/v1/ws`

## Agent quickstart

- Agent platform guide: [docs/agent-platform.md](docs/agent-platform.md)
- Python SDK: [backend/agent_sdk.py](backend/agent_sdk.py)
- CLI: [backend/scripts/lite_agent.py](backend/scripts/lite_agent.py)

Example bootstrap:

```bash
python3 backend/scripts/lite_agent.py \
  --base-url http://127.0.0.1:8000 \
  bootstrap \
  --email admin@example.com \
  --password '<admin-password>' \
  --agent-name night-desk
```

## Deployment

- Frontend target: Vercel project slug `lite-options-terminal`
- Backend target: Railway service slug `lite-options-api`
- Railway backend deployment runbook: [docs/railway-deployment.md](docs/railway-deployment.md)
- Vercel SPA rewrites and security headers live in [frontend/vercel.json](frontend/vercel.json)
- Railway backend boot configuration lives in [backend/nixpacks.toml](backend/nixpacks.toml)

### Current hosted endpoints

- Frontend: [litetrade.vercel.app](https://litetrade.vercel.app)
- Frontend fallback: [lite-options-terminal.vercel.app](https://lite-options-terminal.vercel.app)
- Backend: [lite-options-api-production.up.railway.app](https://lite-options-api-production.up.railway.app)

### Required deploy-time environment

- `APP_ENV=production`
- `LITE_DATABASE_URL` from Railway PostgreSQL
- `FRONTEND_ORIGIN=https://litetrade.vercel.app`
- `FRONTEND_ORIGIN_REGEX=^https://(litetrade|lite-options-terminal)(-[a-z0-9-]+)?\.vercel\.app$`
- `REFRESH_COOKIE_SECURE=true`
- `REFRESH_COOKIE_SAMESITE=none`
- `JWT_SECRET`
- `DHAN_CLIENT_ID`
- `DHAN_ACCESS_TOKEN`
- `DHAN_P0_SLACK_WEBHOOK_URL`
  Required if you want automatic Slack paging when Dhan auth or realtime market data fails.
- `DHAN_PIN`
- `DHAN_TOTP_SECRET`
  Recommended for full unattended recovery if Dhan `RenewToken` fails or the service restarts after token expiry.
- `ALLOW_PUBLIC_SIGNUP=true`
- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_ADMIN_NAME`
- `BOOTSTRAP_AGENT_KEY`
- `BOOTSTRAP_AGENT_NAME`

### Security posture

- Public signup is supported, but each user is isolated to their own portfolios and account data.
- Each user is isolated to their own `manual` and `agent` portfolios.
- Agent API keys are scoped to a single owned portfolio and cannot trade across users.
- Agents can self-bootstrap or self-signup to retrieve a scoped key without human key provisioning.
- Agent write operations require `idempotency_key`.
- Dhan-compatible agent writes require `correlationId`.
- Agent keys support rotation, expiry, revocation, and throttled `last_used_at` writes.
- Auth cookies are `httpOnly`; state-changing cookie-auth requests require CSRF.
- WebSocket auth uses the session cookie for humans or `Authorization` / `X-API-Key` headers for non-browser clients. URL query secrets are intentionally rejected.
- Open-order processing uses Postgres row locks with `SKIP LOCKED` semantics so multiple replicas do not fill the same pending order twice.
- Chart alerts are persisted per user and currently track the NIFTY spot chart rendered in the dashboard.
- Dhan health is exposed at `GET /api/v1/market/provider-health` so production incidents have a single source of truth.

### Important hosted-signal note

- A Railway service cannot read your local `/Users/proxy/trading/auto_trader` directory.
- For hosted operation, push signals to `POST /api/v1/agent/signals` instead of relying on filesystem polling.

## Verification

- Backend tests: `python3 -m pytest backend/tests/test_app.py`
- Backend import check: `python3 -m compileall backend`
- Frontend lint: `cd frontend && npm run lint`
- Frontend build: `cd frontend && npm run build`
