# Lite Frontend

React 19 + Vite terminal UI for the Lite paper-trading platform.

## Responsibilities

- Authenticate operators with cookie-backed sessions plus an in-memory access token.
- Render the NIFTY dashboard, option chain, orders, positions, funds, analytics, and settings views.
- Merge REST snapshots with live WebSocket updates without forcing full-page refreshes.
- Keep manual and agent portfolio views isolated per signed-in user.

## Local Development

From `frontend/`:

```bash
npm install
npm run sync:api
npm run dev
```

The frontend sends browser API requests to same-origin `/api/...` paths.
During local development, the Vite dev server proxies those requests to `http://127.0.0.1:8000` by default.

## Environment

- `VITE_DEV_BACKEND_ORIGIN`: Optional Vite dev proxy target. Defaults to `http://127.0.0.1:8000`.
- `VITE_WS_BASE_URL`: Optional explicit WebSocket URL override for unusual hosted setups.

## Scripts

- `npm run dev`: Start the Vite development server.
- `npm run build`: Type-check and produce a production bundle.
- `npm run lint`: Run ESLint across the frontend.
- `npm run sync:api`: Export backend OpenAPI and regenerate `src/lib/api-schema.d.ts`.

## Architecture Notes

- `src/lib/api.ts`: Shared fetch client, auth token handling, CSRF header injection, and typed API wrappers.
- `src/store/useStore.ts`: Central Zustand store for session state, portfolio data, option-chain data, live quote patches, and toasts.
- `src/hooks/useWebSocket.ts`: Cookie-authenticated WebSocket lifecycle with heartbeats, stale-socket detection, and bounded reconnect backoff.
- `src/App.tsx`: Bootstraps session recovery, shared market loading, and per-portfolio polling.

## Session Model

- The backend issues `httpOnly` access and refresh cookies plus a readable CSRF cookie.
- The frontend also stores the short-lived access token in memory so authenticated REST calls can use bearer auth immediately after login or refresh.
- Clearing the session now resets all user-scoped market, portfolio, and order state so one operator cannot inherit another operator's in-memory data after logout or account switching.

## Verification

Run these before shipping UI changes:

```bash
npm run lint
npm run build
```

For full-stack verification, also run the backend checks listed in the root [README](../README.md).
