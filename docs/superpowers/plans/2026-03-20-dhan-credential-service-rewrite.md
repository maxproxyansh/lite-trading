# Dhan Credential Service Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the 745-line `dhan_credential_service.py` to ~150-200 lines with TOTP-only renewal, daily scheduler, and simplified error handling.

**Architecture:** Single file, single renewal mechanism (TOTP), DB-first token loading. No RenewToken, no shared files, no transient error heuristics. Public API preserved exactly — zero consumer changes.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, httpx, dhanhq SDK

**Spec:** `docs/superpowers/specs/2026-03-20-dhan-credential-service-rewrite.md`

---

### Task 1: Write the new credential service

**Files:**
- Rewrite: `backend/services/dhan_credential_service.py` (745 → ~200 lines)

The entire service is rewritten in one shot. The public API is identical — all imports, method signatures, and types stay the same. This is the only production code change.

- [ ] **Step 1: Read current file and spec**

Read `backend/services/dhan_credential_service.py` (the file being replaced) and `docs/superpowers/specs/2026-03-20-dhan-credential-service-rewrite.md` (the design spec) in full.

- [ ] **Step 2: Write the new `dhan_credential_service.py`**

Replace the entire file. The new version must preserve these exact public exports:
- `DhanApiError(reason, message, *, auth_failed=False, payload=None)` — RuntimeError subclass
- `DhanCredentialSnapshot` — frozen dataclass with fields: `configured`, `client_id`, `access_token`, `expires_at`, `token_source`, `last_refreshed_at`, `last_profile_checked_at`, `last_rest_success_at`, `data_plan_status`, `data_valid_until`, `last_lease_issued_at`, `generation`, `totp_regeneration_enabled`
- `dhan_credential_service` — module-level singleton instance of `DhanCredentialService`

Class methods that MUST exist with same signatures:
- `initialize(self, *, force_reload: bool = False) -> None`
- `reset_runtime_state(self) -> None`
- `snapshot(self) -> DhanCredentialSnapshot`
- `configured(self) -> bool`
- `create_client(self) -> Dhanhq`
- `ensure_token_fresh(self, force_profile: bool = False) -> bool`
- `call(self, operation_name: str, fn: Callable[[Dhanhq], T], *, allow_auth_retry: bool = True) -> T`
- `issue_lease(self) -> DhanCredentialSnapshot`
- `scheduled_preopen_rotation(self) -> bool`
- `start_background_tasks(self) -> None` (async)
- `stop_background_tasks(self) -> None` (async)

Internal method that tests monkeypatch (MUST keep signature):
- `_request_json(self, method: str, url: str, **kwargs) -> dict[str, Any]`

Key design decisions to implement:

**Token loading (`_load_from_storage`):**
- DB record is primary. Query `ServiceCredential` where `provider == "dhan"`.
- If DB has a token, use it. Set `_token_source` from the record.
- If DB has no token, fall back to `settings.dhan_access_token` (env). Set `_token_source = "env"`.
- Decode JWT expiry via `_decode_token_expiry()`.
- Load `generation` from DB record (or 0 if no record).

**Token renewal (`_regenerate_via_totp`):**
- Only path. No RenewToken.
- Acquire `_renewal_lock`. Under the lock, check if token is still expired (another thread may have refreshed). If valid, return False.
- Check 2m10s cooldown (`_last_totp_generation_at`). If cooldown active and token valid, skip. If cooldown active and token expired, sleep the remaining cooldown.
- Record attempt time BEFORE calling Dhan.
- Try 3 TOTP candidates (current, -30s, +30s) via `POST https://auth.dhan.co/app/generateAccessToken` with `params={"dhanClientId": ..., "pin": ..., "totp": ...}`.
- Only accept response if it contains `accessToken` or `token` key with a non-empty value.
- On success: fetch profile, apply new token, persist to DB, increment generation.

**`ensure_token_fresh()`:**
- If no access_token: regenerate via TOTP.
- If profile check needed (elapsed > `dhan_profile_check_seconds`): fetch profile. On auth failure, regenerate.
- If token near expiry (remaining <= `dhan_token_renewal_lead_seconds`): regenerate.

**`call()` auth retry:**
- Call `ensure_token_fresh()` first.
- Execute `fn(client)`. If result indicates auth failure and `allow_auth_retry` and `attempt == 1`: call `_regenerate_via_totp()` directly, then retry.

**`_unwrap_sdk_result()`:**
- Preserved from current code with one change: replace `_extract_error_text(payload)` calls with `str(payload)[:500]`. The old `_extract_error_text` recursive visitor is deleted — `str()` on a dict is sufficient for substring matching on error markers.
- Auth check inlined: `any(m in str(payload).lower() for m in AUTH_ERROR_MARKERS)`.

**`_request_json()`:**
- New signature: `_request_json(self, method: str, url: str, **kwargs) -> dict[str, Any]`. The `**kwargs` are passed through to `httpx.request()` (accepts `headers`, `params`, `timeout`, etc.). The old `failure_reason` and `auth_failed` parameters are REMOVED — the method determines auth failure from the HTTP response itself.
- Simplified error handling. On HTTP >= 400:
  - Check if auth failure: status 401/403 or auth markers in `str(payload).lower()`.
  - Check if rate limited: "too many request" markers or status 429.
  - Check if static IP: "static ip" / "whitelisted ip" markers.
  - Raise `DhanApiError` with appropriate `reason` string and `auth_failed` flag.
- Error message: `str(payload)[:500]` (replaces `_extract_error_text`).

**Scheduler (`_scheduler_loop`):**
- Fire daily at 03:20 UTC (8:50 AM IST). NOT just trading days — every day.
- `_next_rotation_time()` returns tomorrow at 03:20 UTC if today's 03:20 has passed, else today's 03:20.
- On fire: call `scheduled_preopen_rotation()` which calls `_regenerate_via_totp(reason="scheduled-daily-rotation")`.

**Helpers to preserve (same logic, same signatures):**
- `_decode_token_expiry(raw_token: str | None) -> datetime | None`
- `_parse_ist_datetime(value: str | None) -> datetime | None` — uses `IST` from `market_hours` (keep that import; remove `holiday_name` import — no longer needed)
- `_ensure_utc(value: datetime | None) -> datetime | None` — needed by `_load_from_storage` for DB records (SQLite returns naive datetimes)
- `_totp_code(secret: str, *, for_time: float | None = None) -> str`
- `_totp_candidates(secret: str) -> list[str]`
- `@staticmethod _next_rotation_time(now: datetime) -> datetime` — returns the next 03:20 UTC. If `now` is before today's 03:20 UTC, returns today's 03:20. Otherwise returns tomorrow's 03:20. No weekday/holiday filtering — fires every day.

**Internal helpers to preserve:**
- `_apply_new_token(self, *, client_id, access_token, expires_at, token_source, refreshed_at)` — updates state, increments generation, calls `_persist_runtime_state()`
- `_record_profile(self, payload)` — updates `_expires_at`, `_data_plan_status`, `_data_valid_until` from profile response, calls `_persist_runtime_state()`
- `_persist_runtime_state(self)` — upserts `ServiceCredential` record to DB. Called from `_apply_new_token`, `_record_profile`, `issue_lease`, and `_load_from_storage`
- `_fetch_profile(self, client_id, access_token)` — calls `GET /v2/profile` with `access-token` and `client-id` headers (the `_headers()` static method is inlined here since this is the only caller)

**Constants to preserve:**
- `DHAN_API_BASE = "https://api.dhan.co/v2"`
- `DHAN_AUTH_BASE = "https://auth.dhan.co/app"`
- `AUTH_ERROR_MARKERS` tuple
- `RATE_LIMIT_MARKERS` tuple
- `STATIC_IP_MARKERS` tuple

- [ ] **Step 3: Verify file is under 200 lines**

Run: `wc -l backend/services/dhan_credential_service.py`
Expected: under 200 lines. If over, look for opportunities to inline or simplify. Hard ceiling: 250 lines (the spec allows up to 300 but targets ~200).

- [ ] **Step 4: Verify syntax**

Run: `cd backend && python -c "import services.dhan_credential_service; print('OK')"`
Expected: `OK` with no import errors.

- [ ] **Step 5: Commit**

```bash
git add backend/services/dhan_credential_service.py
git commit -m "refactor: rewrite dhan credential service — TOTP only, daily scheduler

Rewrites the 745-line dhan_credential_service.py to ~200 lines.
Removes dead RenewToken path (DH-905), transient error heuristics,
shared file reading, and two-phase renewal chain. Single TOTP renewal
path. Scheduler fires daily (not just trading days) since tokens
expire every 24 hours regardless of market schedule.

Public API unchanged — zero consumer changes needed."
```

---

### Task 2: Update tests

**Files:**
- Modify: `backend/tests/test_app.py` (lines 2194-2302)

The two existing credential service tests assume a RenewToken path that no longer exists. Replace them with one TOTP-only test. Add a scheduler test for weekend firing.

- [ ] **Step 1: Replace `test_dhan_credential_service_renews_and_persists_token` (lines 2194-2248)**

This test sets `dhan_pin=None` and `dhan_totp_secret=None` (TOTP disabled) and expects RenewToken to work. Since RenewToken is gone, replace with a test that verifies TOTP regeneration when the token is near expiry:

```python
def test_dhan_credential_service_regenerates_token_via_totp(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_test_runtime()
    now = datetime(2026, 3, 14, 3, 45, tzinfo=timezone.utc)
    expired_token = _fake_dhan_token(issued_at=now - timedelta(hours=23), expires_at=now + timedelta(minutes=20))
    regenerated_token = _fake_dhan_token(issued_at=now, expires_at=now + timedelta(days=1))

    db = SessionLocal()
    try:
        db.query(ServiceCredential).delete()
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_access_token", expired_token)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_pin", "4321")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_totp_secret", "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_token_renewal_lead_seconds", 3600)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_profile_check_seconds", 900)

    def fake_request_json(method: str, url: str, **kwargs):
        if url.endswith("/profile"):
            headers = kwargs.get("headers") or {}
            if headers.get("access-token") == regenerated_token:
                return {
                    "dhanClientId": "1103337749",
                    "tokenValidity": "15/03/2026 10:00",
                    "dataPlan": "Active",
                    "dataValidity": "2026-04-03 21:50:36.0",
                }
            raise DhanApiError("DHAN_PROFILE_FAILED", "token expired", auth_failed=True)
        if url.endswith("/generateAccessToken"):
            return {
                "accessToken": regenerated_token,
                "expiryTime": "2026-03-15T10:00:00.000",
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(dhan_credential_service, "_request_json", fake_request_json)

    dhan_credential_service.reset_runtime_state()
    dhan_credential_service.initialize(force_reload=True)

    assert dhan_credential_service.ensure_token_fresh() is True
    snapshot = dhan_credential_service.snapshot()
    assert snapshot.access_token == regenerated_token
    assert snapshot.token_source == "totp"

    db = SessionLocal()
    try:
        stored = db.query(ServiceCredential).filter(ServiceCredential.provider == "dhan").first()
        assert stored is not None
        assert stored.access_token == regenerated_token
        assert stored.token_source == "totp"
    finally:
        db.close()
```

- [ ] **Step 2: Delete `test_dhan_credential_service_falls_back_to_totp_regeneration` (lines 2250-2302)**

This test verified the RenewToken → TOTP fallback chain. Remove it entirely. The new test in Step 1 covers the TOTP path directly.

- [ ] **Step 3: Add scheduler weekend test**

Add after the new TOTP test:

```python
def test_dhan_scheduler_fires_on_weekends() -> None:
    """Scheduler must fire daily, not just on trading days."""
    from services.dhan_credential_service import DhanCredentialService

    # Saturday 2026-03-21 at 04:00 UTC (after 03:20 target)
    saturday = datetime(2026, 3, 21, 4, 0, tzinfo=timezone.utc)
    next_run = DhanCredentialService._next_rotation_time(saturday)
    # Should be Sunday 03:20 UTC, not skip to Monday
    assert next_run.weekday() == 6  # Sunday
    assert next_run.hour == 3
    assert next_run.minute == 20

    # Sunday 2026-03-22 at 01:00 UTC (before 03:20 target)
    sunday_early = datetime(2026, 3, 22, 1, 0, tzinfo=timezone.utc)
    next_run = DhanCredentialService._next_rotation_time(sunday_early)
    # Should be today (Sunday) at 03:20 UTC
    assert next_run.day == 22
    assert next_run.hour == 3
    assert next_run.minute == 20
```

Note: The method name is `_next_rotation_time` in the new code (replaces `_next_preopen_rotation_after`). It's a `@staticmethod` that takes a `datetime` and returns the next 03:20 UTC. Adjust if the implementation uses a different name.

- [ ] **Step 4: Run all tests**

Run: `cd backend && python -m pytest tests/test_app.py -v --tb=short 2>&1 | tail -40`
Expected: all tests pass. Pay special attention to:
- `test_dhan_credential_service_regenerates_token_via_totp` — PASS
- `test_dhan_scheduler_fires_on_weekends` — PASS
- `test_market_provider_health_route_reports_runtime_state` — PASS (uses `snapshot`)
- `test_internal_dhan_lease_route_requires_authority_key_and_returns_snapshot` — PASS (uses `DhanCredentialSnapshot` constructor)
- `test_dhan_incident_dedupe_persists_and_provider_health_reports_runtime_fields` — PASS (uses `snapshot`)

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_app.py
git commit -m "test: update credential service tests for TOTP-only rewrite

Replace RenewToken test with TOTP regeneration test. Remove
RenewToken→TOTP fallback test (path no longer exists). Add scheduler
weekend firing test."
```

---

### Task 3: Delete dead artifacts

**Files:**
- Delete: `~/.dhan/token.json`
- Delete: `/Users/proxy/trading/auto_trader_claude_impl/renew_dhan_token.py`

- [ ] **Step 1: Delete the shared token file**

```bash
rm ~/.dhan/token.json
```

Verify: `ls ~/.dhan/token.json` should say "No such file".

- [ ] **Step 2: Delete the auto_trader cron script**

```bash
rm /Users/proxy/trading/auto_trader_claude_impl/renew_dhan_token.py
```

Note: The rest of `auto_trader_claude_impl/` is an archive (skill + credentials). Only this script is deleted.

- [ ] **Step 3: Verify no cron references**

Run: `crontab -l 2>/dev/null | grep -i dhan || echo "No dhan crontab entries"`
Expected: "No dhan crontab entries"

- [ ] **Step 4: Commit** (if inside a git repo for the deleted files — skip if not tracked)

The token file and cron script are outside the lite repo, so no git commit needed for them. Just verify they're gone.

---

### Task 4: Verify TOTP regeneration against real Dhan API

**Files:** None (verification only)

This is the critical integration check. The current running backend has a token expiring 2026-03-21. After deploying the rewrite, verify the new code can regenerate.

- [ ] **Step 1: Restart the backend with the new code**

```bash
cd /Users/proxy/trading/lite/backend
# If running via uvicorn, restart:
# Kill existing, then:
uvicorn main:app --host 0.0.0.0 --port 8000 &
```

- [ ] **Step 2: Check credential snapshot**

```python
import sys; sys.path.insert(0, 'backend')
from services.dhan_credential_service import dhan_credential_service
dhan_credential_service.initialize()
s = dhan_credential_service.snapshot()
print(f'configured: {s.configured}')
print(f'token_source: {s.token_source}')
print(f'expires_at: {s.expires_at}')
print(f'generation: {s.generation}')
print(f'totp_enabled: {s.totp_regeneration_enabled}')
```

Expected: `configured: True`, `totp_enabled: True`, token loaded from DB.

- [ ] **Step 3: Force a TOTP regeneration**

```python
result = dhan_credential_service.scheduled_preopen_rotation()
print(f'rotated: {result}')
s = dhan_credential_service.snapshot()
print(f'new token_source: {s.token_source}')
print(f'new expires_at: {s.expires_at}')
print(f'new generation: {s.generation}')
```

Expected: `rotated: True`, `token_source: totp`, `expires_at` ~24h from now, generation incremented.

- [ ] **Step 4: Verify profile data loaded**

```python
s = dhan_credential_service.snapshot()
print(f'data_plan: {s.data_plan_status}')
print(f'data_valid_until: {s.data_valid_until}')
```

Expected: `data_plan: Active`, `data_valid_until` is a future date.

---

### Task 5: Update memory files

**Files:**
- Modify: `/Users/proxy/.claude/projects/-Users-proxy/memory/project_dhan_token_status.md`
- Create: `/Users/proxy/.claude/projects/-Users-proxy/memory/feedback_dhan_credential_rules.md`
- Modify: `/Users/proxy/.claude/projects/-Users-proxy/memory/MEMORY.md`

- [ ] **Step 1: Update token status memory**

Replace the content of `project_dhan_token_status.md` with the current state after the rewrite. Key facts: Lite is sole authority, TOTP-only, daily scheduler, DB is authoritative store, no shared files.

- [ ] **Step 2: Create architectural rules memory**

Create `feedback_dhan_credential_rules.md` with the rules that prevent regression:
- File must stay under 300 lines
- One renewal mechanism only (currently TOTP)
- Scheduler must fire daily (not just trading days)
- DB is the token store; .env is bootstrap-only
- Never re-add RenewToken path (DH-905)
- Never add shared state files (~/.dhan/)

- [ ] **Step 3: Update MEMORY.md index**

Add pointer to the new feedback memory file.

- [ ] **Step 4: Commit memory updates**

```bash
cd /Users/proxy/.claude/projects/-Users-proxy/memory
git add project_dhan_token_status.md feedback_dhan_credential_rules.md MEMORY.md
git commit -m "memory: update dhan token rules after credential service rewrite"
```
