# Main Branch Hardening Review

This branch hardens the main backend and operator flows around four concerns:

- account bootstrap and operator lifecycle
- user and portfolio isolation
- agent-scoped trading safety
- deployment and runtime documentation

## Findings addressed

### 1. Broken bootstrap contract

Main had drifted into a state where tests and the seed script still expected `ensure_bootstrap_state`, but the implementation no longer existed. Startup also no longer ensured any operator account.

Fix:

- restored `ensure_bootstrap_state`
- startup now creates or syncs the configured bootstrap admin
- seed script and tests work again

### 2. Cross-account access from newly created users

Main exposed `/api/v1/auth/signup`, but the real bug was not signup itself. The problem was that user creation and portfolio ownership were not strict enough to guarantee account isolation.

Fix:

- public signup remains supported
- each signed-up user gets isolated `manual` and `agent` portfolios
- routes continue to enforce user-owned portfolio access only

### 3. Agent keys were effectively global

Agent API keys were not tied to a user or portfolio. Any valid key with write scopes could submit orders against any `portfolio_id`.

Fix:

- agent keys now carry `user_id` and `portfolio_id`
- legacy unscoped keys are rejected
- agent order, funds, positions, and close flows are bound to the key’s scoped portfolio
- agent writes now require `idempotency_key`
- added agent read routes for orders and positions

### 4. Inconsistent user portfolio lifecycle

Users only received a single default portfolio, while the product model expects separate manual and agent trading lanes.

Fix:

- each user is ensured to have both `manual` and `agent` portfolios
- portfolio summaries now include `kind`
- bootstrap agent keys are automatically pointed at the owned `agent` portfolio

### 5. Runtime drift and operational ambiguity

Docs still implied default credentials and older hosted behavior.

Fix:

- updated `README.md`
- updated `backend/.env.example`
- preserved Railway deployment runbook

## Security and privacy notes

- Cookie auth stays `httpOnly`
- CSRF remains mandatory for state-changing cookie-auth requests
- CORS stays explicit and credentialed
- auth responses are marked `Cache-Control: no-store`
- backend responses now include a restrictive API CSP header
- rate limiting is still in-memory, but now synchronized and prunes empty buckets

## Trading-system notes

- order placement still uses row locking where the database supports it
- order idempotency is now backed by a unique index rather than best-effort checks alone
- analytics were tightened so closed-trade win/loss and P&L matching are closer to actual fills
- signal actionability no longer becomes false just because advisory target or stop fields are malformed

## Residual limitations

- money is still stored in floating columns in the database; calculations use `Decimal`, but a full `NUMERIC` migration has not been introduced yet
- websocket auth is secure, but there is still no per-event authorization beyond connection-level auth
- there is still no full Alembic migration framework; schema drift is handled by startup migrations
