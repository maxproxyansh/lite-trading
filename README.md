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

4. Default bootstrap login:

   - Email: `admin@lite.trade`
   - Password: `lite-admin-123`

## Key endpoints

- Human auth: `/api/v1/auth/*`
- Trading: `/api/v1/orders`, `/api/v1/positions`, `/api/v1/funds`, `/api/v1/analytics`
- Market data: `/api/v1/market/*`
- Signals: `/api/v1/signals`
- Agent API: `/api/v1/agent/*`
- WebSocket: `/api/v1/ws`

## Deployment

- Frontend target: Vercel project slug `lite-options-terminal`
- Backend target: Railway service slug `lite-options-api`
- Railway backend deployment runbook: [docs/railway-deployment.md](/Users/proxy/trading/lite/docs/railway-deployment.md)
- Vercel SPA rewrites and security headers live in [frontend/vercel.json](/Users/proxy/trading/lite/frontend/vercel.json)
- Railway backend boot configuration lives in [backend/nixpacks.toml](/Users/proxy/trading/lite/backend/nixpacks.toml)

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
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_AGENT_KEY`

### Important hosted-signal note

- A Railway service cannot read your local `/Users/proxy/trading/auto_trader` directory.
- For hosted operation, push signals to `POST /api/v1/agent/signals` instead of relying on filesystem polling.

## Verification

- Backend tests: `python3 -m pytest backend/tests/test_app.py`
- Backend import check: `python3 -m compileall backend`
- Frontend lint: `cd frontend && npm run lint`
- Frontend build: `cd frontend && npm run build`
