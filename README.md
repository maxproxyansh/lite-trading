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
- Backend target: Render web service slug `lite-options-api`
- Use `frontend/vercel.json` for SPA rewrites and `render.yaml` for the backend service plus Postgres blueprint.

## Verification

- Backend tests: `python3 -m pytest backend/tests/test_app.py`
- Backend import check: `python3 -m compileall backend`
- Frontend lint: `cd frontend && npm run lint`
- Frontend build: `cd frontend && npm run build`
