# Dhan Market-Open Incident RCA and Fix Spec

Date: 2026-03-23  
Owner: Lite backend / local trading runtime

## Incident Summary

At market open on March 23, 2026, the platform returned a mix of Dhan auth failures, token-regeneration failures, and market-data `503` errors.

The production backend on Railway did recover on its own a few minutes later, but the recovery path was wrong and slow. At the same time, local OpenClaw trading jobs were still pointed at legacy direct-Dhan scripts, so the overall platform looked broken even after Railway recovered.

## What Actually Happened

### Production timeline

All timestamps below are from Railway logs for the live production deployment.

- `02:23:04 UTC` / `07:53:04 IST`
  - Lite ran a scheduled token regeneration through Dhan `generateAccessToken`.
  - Log: token regenerated successfully via scheduled renewal.

- `02:35:14 UTC` / `08:05:14 IST`
  - `/api/v1/market/chain?expiry=2026-03-30` returned `503`.

- `02:35:32 UTC` / `08:05:32 IST`
  - `/api/v1/market/chain?expiry=2026-04-07` returned `503`.

- `02:53:28 UTC` / `08:23:28 IST`
  - Lite profile check against Dhan returned `400`.
  - This is the first hard proof that the current token had become unacceptable to Dhan even though Lite still had a local expiry timestamp for it.

- `02:53:34 UTC` through `02:53:53 UTC`
  - Lite attempted TOTP-based token regeneration.
  - Dhan returned HTTP `200`, but the payload contained `{"message":"Invalid TOTP","status":"error"}` instead of a token.

- `02:53:53 UTC` through `02:54:04 UTC`
  - Lite logged `Skipping TOTP regen (... cooldown, token valid)`.
  - During this period Lite still trusted local JWT expiry even though Dhan had already rejected the token via `/profile`.
  - User-facing market endpoints returned `503`.

- `02:58:46 UTC` / `08:28:46 IST`
  - Lite attempted token regeneration again after the cooldown window.
  - Regeneration succeeded and profile checks went healthy again.
  - Slack incident notification was sent after recovery.

### Local runtime timeline

- OpenClaw’s active `nifty-morning-plan` job ran at `08:30 IST`.
- Its `nifty-trader` skill still pointed at the old `auto_trader` flow.
- Because the old path was missing or stale, the agent fell back to `auto_trader_claude_impl`.
- That path failed with a local Dhan token-expired error.

This means the market-open failure was not only a Railway incident. A live local trading-analysis path was also still wired to old direct-Dhan code.

## Root Causes

### 1. Failed TOTP attempts were treated like successful token generations

Lite started a two-minute cooldown immediately after calling `generateAccessToken`, even when Dhan returned an error payload and no token was minted.

Effect:
- A bad TOTP window or edge-of-window attempt created an artificial recovery freeze.
- Lite then refused to retry for roughly two minutes.

Why this matters:
- The broker was already rejecting the token.
- The cooldown should only have applied after a real token generation success or a broker-enforced rate-limit response.

### 2. Lite trusted local expiry after broker rejection

Once `/profile` rejected the token, Lite should have considered that token generation dead immediately.

Instead, the old logic still asked:
- does the JWT look locally unexpired?

Effect:
- Lite skipped recovery even though Dhan had already said the token was bad.
- This turned a recoverable auth incident into user-facing `503` errors.

### 3. Planned refresh used TOTP as the primary path

Lite was using TOTP-based `generateAccessToken` for planned rotation, not just emergency recovery.

Effect:
- A fragile emergency mechanism was carrying too much routine load.
- That increased exposure to TOTP window timing issues and Dhan’s token-generation rules.

### 4. There were still live local Dhan paths outside Lite

OpenClaw trading jobs were still:
- invoking a `nifty-trader` skill that pointed at stale `auto_trader` scripts
- running three enabled intraday cache jobs against `auto_trader_claude_impl/cache_intraday.py`

Effect:
- Even when Lite was the intended Dhan authority, the user still had active local jobs hitting old Dhan code.
- This created a second failure surface and made incidents look larger and more random than they were.

## Things Ruled Out

### Not a missing-secret problem

Railway production had:
- `DHAN_PIN`
- `DHAN_TOTP_SECRET`
- Slack webhook configured

The incident happened even though those secrets were present.

### Not a multi-replica Railway race

Railway production was verified to be running with:
- `numReplicas = 1`

So this was not caused by two production replicas rotating tokens against each other.

### Not a data-plan-expired incident

Live provider health after recovery showed:
- `data_plan_status = Active`

So the incident was not caused by a lapsed Dhan data subscription.

## Fix Spec

### A. Lite remains the only supported Dhan authority

Requirements:
- Lite owns Dhan token validation, planned refresh, and emergency recovery.
- No local trading automation is allowed to rotate or regenerate Dhan credentials outside Lite.

Implementation:
- Keep planned token management inside Lite only.
- Disable legacy direct-Dhan local cache jobs.
- Point OpenClaw trading analysis at Max tools, which already read market data through Lite.

### B. Treat broker rejection as the source of truth

Requirements:
- Once Dhan rejects a token, Lite must stop trusting the token’s local expiry timestamp.

Implementation:
- Mark the current token generation as dead on any auth-rejected profile or SDK response.
- Force recovery from that dead generation instead of waiting because the JWT still looks unexpired locally.

### C. Separate planned refresh from emergency regeneration

Requirements:
- Routine token refresh should use the lighter active-token path first.
- TOTP should be the fallback and emergency path, not the default for everything.

Implementation:
- Planned refresh uses `RenewToken` first.
- If `RenewToken` fails, Lite falls back to TOTP-based `generateAccessToken`.
- Pre-open refresh uses the same single path; no forced TOTP rotation.

### D. TOTP recovery must be boundary-aware, not cooldown-blind

Requirements:
- Invalid-TOTP responses should trigger a short retry on the next TOTP window.
- Two-minute waits should only happen after a real successful token generation or a true Dhan rate-limit response.

Implementation:
- Do not start the two-minute cooldown on failed invalid-TOTP payloads.
- Retry once on the next TOTP boundary.
- Only use the long cooldown for real Dhan rate-limit behavior.

### E. Do not leak auth URLs or secrets into logs

Requirements:
- Logs must never contain auth query params like `pin` or `totp`.

Implementation:
- Mute `httpx` and `httpcore` info logs in production startup.
- Report Dhan endpoint labels, not full auth URLs, in error messages.

### F. Local trading analysis must use Max/Lite, not legacy Dhan scripts

Requirements:
- OpenClaw morning, midday, and evening Nifty jobs must work from the supported Max toolset.

Implementation:
- Update the `nifty-trader` skill to use:
  - `python3 /Users/proxy/trading/max/tools/market.py ...`
  - `python3 /Users/proxy/trading/max/tools/journal.py ...`
- Disable the three `cache_intraday.py` jobs that still hit Dhan directly through `auto_trader_claude_impl`.

## Acceptance Criteria

This incident class is only considered fixed if all of the following are true.

### Backend behavior

- A broker-rejected token is never treated as healthy because of local JWT expiry.
- Failed invalid-TOTP attempts do not start a two-minute freeze.
- Planned refresh does not force TOTP by default.
- Startup and pre-open refresh do not leak Dhan auth URLs into logs.

### Local runtime behavior

- OpenClaw Nifty analysis no longer points at `auto_trader` or `auto_trader_claude_impl`.
- No enabled OpenClaw cron job directly calls legacy Dhan reader scripts.

### Verification

- Focused Dhan credential tests pass.
- Full Lite backend test suite passes.
- Backend compiles cleanly.
- Max market snapshot works against live Lite after the change.
- Railway deploy starts cleanly.
- Live `provider-health`, `snapshot`, `chain`, and candle endpoints stay healthy after deploy.

## Residual Truth

This fix removes the platform-caused token churn and recovery bugs. It does not make Dhan itself infallible.

What this fix is designed to guarantee:
- the platform will not keep a broker-rejected token alive because of local expiry bookkeeping
- the platform will not freeze recovery after a failed invalid-TOTP attempt
- the platform will not route live local trading analysis through stale direct-Dhan code

That is the correct boundary for “fixed on our side.”
