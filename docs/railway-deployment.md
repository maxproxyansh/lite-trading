# Railway Deployment

This document is the deployment runbook for the Lite backend on Railway.

## Target services

- Railway project: `lite-options-api`
- Railway web service: `lite-options-api`
- Railway Postgres: managed PostgreSQL inside the same project
- Public backend URL: `https://lite-options-api-production.up.railway.app`
- Public frontend URLs:
  - `https://litetrade.vercel.app`
  - `https://lite-options-terminal.vercel.app`

## Backend source layout

- Railway service root: `backend`
- Build/start config: [backend/nixpacks.toml](/Users/proxy/trading/lite/backend/nixpacks.toml)
- App entrypoint: [backend/main.py](/Users/proxy/trading/lite/backend/main.py)

## One-time Railway setup

1. Create a Railway project.
2. Add a PostgreSQL service to the project.
3. Add the backend service from the GitHub repository.
4. Set the backend root directory to `backend`.
5. Ensure Railway uses the Nixpacks config from [backend/nixpacks.toml](/Users/proxy/trading/lite/backend/nixpacks.toml).

## Railway CLI

If you prefer a CLI workflow, install Railway CLI:

```bash
npm install -g @railway/cli
```

For interactive auth:

```bash
railway login
```

For non-interactive auth on this machine, Railway CLI expects `RAILWAY_API_TOKEN`, not `RAILWAY_TOKEN`.

```bash
export RAILWAY_API_TOKEN="<railway account token>"
railway whoami
```

Useful commands:

```bash
railway whoami
railway project link
railway status
railway variable list
railway up
railway redeploy
```

## Required environment variables

Set these on the Railway backend service:

- `APP_ENV=production`
- `LITE_DATABASE_URL`
  Use the Railway Postgres connection string.
- `FRONTEND_ORIGIN=https://litetrade.vercel.app`
- `FRONTEND_ORIGIN_REGEX`
  Set this if you want both production and preview Vercel domains to work:
  `^https://(litetrade|lite-options-terminal)(-[a-z0-9-]+)?\.vercel\.app$`
- `REFRESH_COOKIE_SECURE=true`
- `REFRESH_COOKIE_SAMESITE=none`
- `ALLOW_PUBLIC_SIGNUP=true`
- `JWT_SECRET`
  Use a long random secret.
- `DHAN_CLIENT_ID`
- `DHAN_ACCESS_TOKEN`
- `BOOTSTRAP_ADMIN_EMAIL`
  Recommended so you always have an operator account even when public signup is enabled.
- `BOOTSTRAP_ADMIN_PASSWORD`
  Set this explicitly in production.
- `BOOTSTRAP_ADMIN_NAME`
  Recommended.
- `BOOTSTRAP_AGENT_KEY`
  Set this explicitly in production.
- `BOOTSTRAP_AGENT_NAME`
  Optional.
- `AUTO_EXECUTE_SIGNALS=false`
  Recommended unless you intentionally enable automated paper trades.

## Vercel environment variables

Set these on the frontend project in Vercel:

- `VITE_API_BASE_URL=https://lite-options-api-production.up.railway.app`
- `VITE_WS_BASE_URL=wss://lite-options-api-production.up.railway.app/api/v1/ws`

Then redeploy the frontend.

## Deploying a new backend revision

### Preferred path

1. Push the desired commit to GitHub.
2. In Railway, open the `lite-options-api` service.
3. Trigger a deploy for the target commit.
4. Wait for deployment status `SUCCESS`.
5. Verify the bootstrap admin can sign in and generate a portfolio-scoped agent key.

### CLI path

After `railway login` or exporting `RAILWAY_API_TOKEN`:

```bash
cd backend
railway project link \
  -p fed5f197-2182-44f5-b742-335c243e15ee \
  -e d09e621f-fb95-4096-8468-b9fa15a195bb \
  -s 5689451f-4d26-40a3-9a05-5e23db670113
railway up
```

Or, if the service is already linked and you only changed environment values:

```bash
railway redeploy
```

To update CORS from the CLI:

```bash
railway variable set \
  FRONTEND_ORIGIN=https://litetrade.vercel.app \
  FRONTEND_ORIGIN_REGEX='^https://(litetrade|lite-options-terminal)(-[a-z0-9-]+)?\.vercel\.app$' \
  --service 5689451f-4d26-40a3-9a05-5e23db670113 \
  --environment d09e621f-fb95-4096-8468-b9fa15a195bb
railway redeploy -s 5689451f-4d26-40a3-9a05-5e23db670113 -y
```

### What to verify after deploy

Run these smoke checks:

```bash
curl https://lite-options-api-production.up.railway.app/
```

Expected:

```json
{"status":"ok","app":"Lite Options Terminal","environment":"production"}
```

Then verify:

1. Admin login succeeds.
2. `GET /api/v1/market/snapshot` returns a non-error response.
3. `GET /api/v1/market/chain` returns rows when Dhan credentials are valid.
4. `POST /api/v1/agent/signals` works with the configured agent key.
5. Portfolio-scoped agent key can place an order only on its bound `agent` portfolio.
6. WebSocket connection to `/api/v1/ws` succeeds for an authenticated session.

## Dhan credential rotation

If Dhan market data starts failing:

1. Generate or retrieve the current working `DHAN_ACCESS_TOKEN`.
2. Update `DHAN_ACCESS_TOKEN` in Railway.
3. Trigger a fresh Railway deploy.
4. Re-check:
   - `/api/v1/market/expiries`
   - `/api/v1/market/chain`
   - `/api/v1/market/candles`

## Hosted signal ingestion

Do not rely on Railway reading a local filesystem path such as `/Users/proxy/trading/auto_trader`.

Use:

- `POST /api/v1/agent/signals`
- Header: `X-API-Key: <agent key>`

This is the supported hosted path for signal ingestion.

## Rollback

If a bad backend revision is deployed:

1. Open the Railway deployment history for `lite-options-api`.
2. Redeploy the last known good deployment.
3. Re-run the smoke checks above.

## Local verification before shipping

Run these before pushing a deploy candidate:

```bash
python3 -m pytest backend/tests/test_app.py
python3 -m compileall backend
npm --prefix frontend run lint
npm --prefix frontend run build
```
