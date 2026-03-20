# Dhan Credential Service Rewrite

**Date:** 2026-03-20
**Status:** Draft
**Approach:** Clean rewrite (Option B) — single file, ~150-200 lines

## Problem

`dhan_credential_service.py` is 745 lines accumulated across 10+ fix sessions. Each session added edge-case handling without simplifying the core. The result:

- RenewToken path is dead code (TOTP tokens can't be renewed, DH-905)
- Shared file reading was added then silently removed by another AI session
- `.env` token is permanently stale (never written back after TOTP regeneration)
- Scheduler skips weekends but tokens expire every 24 hours
- Transient error guard is bypassed in every real failure case
- Generation counter has load-from-DB gymnastics that serve no purpose
- `~/.dhan/token.json` and `auto_trader_claude_impl/renew_dhan_token.py` are dead artifacts

## Design

### Scope

Rewrite `backend/services/dhan_credential_service.py` to ~150-200 lines. Delete dead artifacts. Fix the scheduler. No consumer changes.

### What stays (public API)

Every consumer-facing method and type keeps the same signature:

- `DhanApiError(reason, message, *, auth_failed, payload)`
- `DhanCredentialSnapshot` dataclass (all current fields preserved)
- `dhan_credential_service.initialize(force_reload=bool)`
- `dhan_credential_service.reset_runtime_state()`
- `dhan_credential_service.configured() -> bool`
- `dhan_credential_service.create_client() -> Dhanhq`
- `dhan_credential_service.snapshot() -> DhanCredentialSnapshot`
- `dhan_credential_service.ensure_token_fresh(force_profile=bool) -> bool`
- `dhan_credential_service.call(operation_name, fn, *, allow_auth_retry=bool) -> T`
- `dhan_credential_service.issue_lease() -> DhanCredentialSnapshot`
- `dhan_credential_service.start_background_tasks()` / `stop_background_tasks()`
- `dhan_credential_service.scheduled_preopen_rotation() -> bool`

### What's deleted

| Item | Reason |
|------|--------|
| `_renew_access_token()` method | TOTP tokens can't use RenewToken (DH-905). Token source is always "totp" now. Dead code. |
| `renew_access_token()` public method | Not called by any consumer. Was only reachable through internal `_refresh_or_regenerate`. |
| `_refresh_or_regenerate()` | Replaced by `_regenerate_if_needed()`. The two-phase "try renew then TOTP" dance is unnecessary with only one path. |
| Transient error guard | Only blocks `scheduled-renewal`, which already passes through because remaining <= lead time. Dead logic that obscures flow. |
| Shared file reading | Code was already removed. `~/.dhan/token.json` is a dead artifact. |
| `_extract_error_text()` recursive visitor | Over-engineered for error formatting. Replaced by `str(payload)[:500]` for error messages in `_request_json` and `_unwrap_sdk_result`. Same truncation limit, simpler code. |
| `~/.dhan/token.json` file | Dead artifact from deleted auto_trader cron. |
| `auto_trader_claude_impl/renew_dhan_token.py` | Dead script, cron removed, uses wrong HTTP method. |

### What changes

**1. Single renewal path: TOTP only**

```
ensure_token_fresh()
  -> token expired or missing?
     -> _regenerate_via_totp()
        -> POST /app/generateAccessToken with 3 TOTP candidates
        -> _fetch_profile() on new token
        -> _apply_new_token() persists to DB + increments generation

call() auth-retry:
  -> fn(client) raises auth error on attempt 1?
     -> _regenerate_via_totp()
     -> retry fn(client) with new token
```

No RenewToken. No shared file re-read. No two-phase fallback chain. Both `ensure_token_fresh()` and `call()`'s auth-retry use the same `_regenerate_via_totp()` directly.

**2. Token loading priority: DB first, .env fallback**

`_load_from_storage()` simplified:
- **DB record** is authoritative. If the DB has a token, use it.
- **`.env` / Railway env var** is bootstrap-only — used on first deploy when DB has no record, or if DB token is missing.
- No more "pick whichever has the latest expiry" comparison. DB wins. `.env` is fallback for cold start.

**3. Scheduler runs every day, not just trading days**

Tokens expire in 24 hours regardless of market schedule. The scheduler fires daily at 03:20 UTC (8:50 AM IST). On weekends and holidays it still regenerates the token. The only condition: TOTP credentials must be configured.

**4. Thread safety simplified**

Keep `_renewal_lock` to prevent concurrent TOTP calls. Under the lock: check if token is still valid (another thread may have refreshed while waiting), if so return early. Otherwise regenerate. No generation-before-lock pattern.

**5. TOTP rate limiting preserved**

Keep the 2m10s cooldown tracking. Record attempt time before calling Dhan. Sleep if rate-limited and token is expired. Skip if rate-limited and token is still valid. Inherited risk: `time.sleep()` blocks the caller thread for up to 130s. This is acceptable because callers use `asyncio.to_thread()` for the blocking paths.

**6. Error classification simplified**

`_request_json` handles all HTTP errors inline. Two categories:
- Auth failure (401/403 or auth error markers in response) -> `DhanApiError(auth_failed=True)`
- Everything else -> `DhanApiError(auth_failed=False)`

Rate limit and static IP markers stay for informational `reason` strings but don't change control flow. Consumers (market_data.py) handle rate limits at their level.

**7. `_unwrap_sdk_result` preserved with inline auth check**

This method handles dhanhq SDK responses (dict with `status`/`data`/`remarks` keys). Currently calls `_looks_like_auth_error()` — that standalone method is removed, but the same marker check is inlined into both `_unwrap_sdk_result` and `_request_json`. It's 2 lines: `text = str(payload).lower()` + `any(m in text for m in AUTH_ERROR_MARKERS)`.

**8. Internal helpers consolidated**

| Current | New |
|---------|-----|
| `_apply_new_token()` | Stays. Updates state + persists to DB + increments generation. |
| `_record_profile()` | Stays. Updates `_expires_at` from profile (authoritative) + `_data_plan_status` + persists. |
| `_headers()` static method | Inlined into `_fetch_profile()` (the only remaining caller). |
| `_load_from_storage()` | Simplified: DB first, .env fallback. No multi-source comparison. |

**9. TOTP credentials sent as query params**

The current code sends `dhanClientId`, `pin`, `totp` as URL query params via `httpx.request(params=...)`. This works (Dhan accepts it; generation counter 309 proves it). We preserve this behavior. Dhan's auth endpoint documentation shows query params as the expected format.

### File structure

One file: `backend/services/dhan_credential_service.py` (~150-200 lines)

Sections:
1. Imports + constants (~15 lines)
2. `DhanApiError` + `DhanCredentialSnapshot` (~25 lines)
3. Helpers: `_decode_token_expiry`, `_parse_ist_datetime`, `_totp_code`, `_totp_candidates` (~40 lines)
4. `DhanCredentialService` class (~100-120 lines)
5. Module-level singleton (~1 line)

### Test contract

Tests monkeypatch `_request_json` wholesale (replacing the entire method). Internal changes to `_request_json` behavior don't break tests. The test-visible contract: `_request_json` is an instance method with signature `(self, method, url, **kwargs)`. This is preserved.

### Cleanup

- Delete `~/.dhan/token.json`
- Delete `/Users/proxy/trading/auto_trader_claude_impl/renew_dhan_token.py` (rest of archive stays)
- Update `.env` comment to note token is a bootstrap fallback, DB is authoritative

### Test changes

Existing tests monkeypatch `_request_json` and `snapshot`. These APIs are preserved. The two credential service tests (`test_dhan_credential_service_renews_and_persists_token`, `test_dhan_credential_service_falls_back_to_totp_regeneration`) get consolidated into one test for the TOTP-only path. RenewToken-specific assertions are removed. Scheduler test added to verify it fires on weekends (not just trading days).

### What prevents this from happening again

1. **300-line hard limit.** The file must stay under 300 lines. If it grows, something is being over-engineered.
2. **One renewal mechanism.** If Dhan adds a new renewal API in the future, replace TOTP — don't add a second path alongside it.
3. **Daily scheduler.** No assumptions about when tokens are needed. Renew daily, period.
4. **No shared state files.** DB is the token store. `.env` is bootstrap-only. No `~/.dhan/` files.
5. **Memory file update.** Update the project memory to record these architectural decisions so future AI sessions don't re-add dead code paths.

### Rollback

No schema changes to `ServiceCredential`. If the rewrite breaks in production, revert to the previous commit. The DB state is forward-compatible — the old code reads the same columns. The stale `.env` token is still there as a fallback.

## Success criteria

- `dhan_credential_service.py` is under 200 lines
- All existing tests pass (with test updates for removed RenewToken path)
- TOTP regeneration works locally (verified against real Dhan API)
- Scheduler fires daily including weekends
- Token survives backend restart (loaded from DB)
- Dead artifacts deleted
