# Platform Audit — 2026-03-11

## Deployment Issues Found & Fixed

### CRITICAL: Backend wasn't deploying

**Problem:** Railway Git Integration was NOT auto-deploying on push to main. The production backend was running code from 12+ hours ago — missing alerts routes, agent market access, option chart history, order modify, and dual-path auth. Every PR we merged (PRs #2, #3, #5, #6, #7) was live on the frontend (Vercel) but NOT on the backend (Railway).

**Root cause:** Railway `rootDir` is set to `backend/`, so `railway up` must be run from the `backend/` directory, not the repo root. The repo-root deploy uploaded frontend files too and failed.

**Fix:** Deploy manually with `cd backend && railway up --detach`. Need to set up Railway Git Integration properly (watch `main` branch, `backend/` root directory) for auto-deploy.

**Action needed:** Configure Railway service to watch the `main` branch with root directory `backend/` so pushes auto-deploy. Until then, manual `railway up` is required after each backend change.

### CRITICAL: Missing OrderModifyRequest schema crashed backend

**Problem:** PR #7 added `modify_order()` in `trading_service.py` which imports `OrderModifyRequest` from `schemas.py`, but the schema class was never defined. This caused an `ImportError` on startup, taking down the entire backend.

**Fix:** Added `OrderModifyRequest` schema with `quantity`, `price`, and `trigger_price` fields. Committed in `95de577`.

### CRITICAL: Missing alert scopes blocked agent key creation

**Problem:** Tests and code expected `alerts:read` and `alerts:write` scopes, but `ALLOWED_AGENT_SCOPES` in `auth_service.py` didn't include them. Any agent bootstrap requesting alert scopes would get a 422 error.

**Fix:** Added both scopes to `DEFAULT_AGENT_SCOPES`. Committed in `95de577`.

### HIGH: Portfolio defaults to agent instead of manual

**Problem:** New users signing up got two portfolios (agent + manual). The store's `setPortfolios` picked `portfolios[0]` which was the agent portfolio. All subsequent API calls (orders, funds, positions, analytics) used the agent portfolio ID with session auth, resulting in 404 errors and error toasts on every page.

**Fix:** Changed `setPortfolios` to prefer `portfolios.find(p => p.kind === 'manual')` as the default. Committed in `bf953c6`.

---

## Verification Results (Post-Fix)

### Working Features
- [x] **Signup/Login** — creates account, redirects to dashboard, "Signed in" toast
- [x] **Manual portfolio auto-selected** — no more 404 cascade
- [x] **NIFTY 50 chart** — daily, 1h, 15m, 5m, 1m timeframes all load with historical data
- [x] **Chart history pagination** — "Loading older..." indicator, scrollback works
- [x] **Options chain** — collapsed view with CE/PE LTP, strike, OI bars
- [x] **Expiry tabs** — 4 visible in collapsed, switchable
- [x] **Chain filters** — FULL/ITM/ATM/OTM work, ATM is default
- [x] **Chart alerts panel** — visible with close button, "Spot" badge, instructions
- [x] **Alerts API** — `/api/v1/alerts` route live (was 404 before fix)
- [x] **Option chart history** — backend route accepts `symbol`/`security_id` params
- [x] **Agent market access** — dual-path auth (session + API key) on all market routes
- [x] **Orders page** — loads correctly, empty state shown
- [x] **Positions page** — loads correctly
- [x] **Funds page** — shows ₹5,00,000 starting cash with proper formatting
- [x] **Analytics page** — loads
- [x] **Glass-morphism toasts** — success/error/info with backdrop-blur
- [x] **WebSocket** — connects after login
- [x] **Zero console errors** — clean browser console after fixes

### Console Errors (Before Fix)
- 50+ errors per minute: `/api/v1/alerts` 404, portfolio 404s, CORS errors during backend restart
- All resolved after deploying backend fix + frontend portfolio default fix

---

## Known Issues (Not Yet Fixed)

### Backend
1. **2 test failures** — `test_agent_alerts_are_portfolio_scoped` and `test_agent_can_modify_open_order_and_partially_close_position` fail because the agent alerts CRUD route and order modify route don't exist yet. These are being built by Codex in the agent UX branch (PR #8).
2. **Railway not auto-deploying** — needs Git Integration configured for `main` branch + `backend/` root.

### Frontend
3. **Ticker bar broken** — S&P, NASDAQ, BTC, Gold, Oil all show "--". NIFTY works. Consider removing or fixing.
4. **Portfolio dropdown truncates names** — both options show "Test Reviewe..." — should show portfolio kind (Manual/Agent).
5. **Change indicator shows +0.00 (0.00%)** — NIFTY change doesn't update outside market hours (expected, but could show previous day's change).

### UX Polish (P2)
6. Missing ₹ prefix on Orders/Positions/History tables
7. Table header casing inconsistent (Title Case vs ALL CAPS)
8. No watchlist feature
9. No keyboard shortcuts
10. No symbol search in options chain

---

## PR Merge History (This Session)

| PR | Title | Status | Notes |
|----|-------|--------|-------|
| #3 | perf: move market data to live delta updates | Merged manually | Rebased over cosmetic changes, resolved conflicts |
| #4 | feat: add autonomous agent trading platform | Closed | Duplicate of #3 |
| #5 | feat: close agent market access and docs gaps | Merged manually | Fixed dropped `before` param, added unauth test |
| #6 | chore: sync generated OpenAPI artifacts | Merged via GitHub | Clean regeneration |
| #7 | feat: add option contract chart history | Merged via GitHub | Uncovered missing OrderModifyRequest schema |
| #8 | Agent P0: alerts, order modification, partial close | Open | Codex working on it |

## Commits to Main (This Session)

1. `perf: cut quote latency across backend and frontend` (PR #3 rebase)
2. `fix: align final latency review tweaks` (PR #3 second commit)
3. `fix: add has_more and next_before to CandleResponse schema`
4. `fix: restore candles pagination, add unauth market test`
5. `feat: close agent market access and docs gaps` (PR #5)
6. `fix: add missing OrderModifyRequest schema and alert scopes`
7. `fix: default portfolio selection to manual instead of agent`
8. `chore: remove accidentally committed worktree submodule`
