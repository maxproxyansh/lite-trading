# Dhan P0 Runbook

This is the production runbook for Dhan auth and realtime market-data incidents.

## Why this used to fail

Before the March 14, 2026 hardening pass, the backend loaded `DHAN_ACCESS_TOKEN` once from environment, never called Dhan `RenewToken`, never persisted renewed tokens, and collapsed upstream auth failures into generic `OPTION_CHAIN_UNAVAILABLE` or `MARKET_FEED_DISCONNECTED` states. That meant the service could loop forever on a dead token with no precise escalation path.

## What is fixed now

- Dhan credentials are managed by a single runtime service.
- The backend checks `/profile`, renews tokens before expiry, and persists the latest working token in the database.
- If `RenewToken` fails and `DHAN_PIN` plus `DHAN_TOTP_SECRET` are configured, the backend regenerates a fresh access token automatically.
- The realtime feed is force-reconnected whenever a token rotates.
- Provider health is exposed at `GET /api/v1/market/provider-health`.
- New P0 incidents page Slack through `DHAN_P0_SLACK_WEBHOOK_URL`.
- Recovery sends a separate Slack resolution alert.

## Required production secrets

- `DHAN_CLIENT_ID`
- `DHAN_ACCESS_TOKEN`
- `DHAN_P0_SLACK_WEBHOOK_URL`
- `DHAN_PIN`
- `DHAN_TOTP_SECRET`

`DHAN_PIN` and `DHAN_TOTP_SECRET` are what make recovery truly unattended after a hard token failure or a restart with an expired token.

## What to check first

1. `GET /api/v1/market/provider-health`
2. Railway logs for the backend service
3. The latest Slack incident message

Key fields in `provider-health`:

- `incident_reason`
- `incident_message`
- `token_expires_at`
- `last_token_refresh_at`
- `last_profile_check_at`
- `last_option_chain_success_at`
- `last_feed_message_at`
- `totp_regeneration_enabled`
- `slack_configured`

## Incident meanings

- `DHAN_AUTH_FAILED`
  Dhan rejected the current token and automatic recovery failed.
- `DHAN_TOKEN_RENEWAL_FAILED`
  `RenewToken` failed and no fallback path recovered it.
- `DHAN_TOKEN_REGENERATION_FAILED`
  TOTP fallback was attempted but failed.
- `DHAN_DATA_PLAN_INACTIVE`
  Dhan profile says market-data entitlement is inactive.
- `OPTION_CHAIN_STALE`
  Dhan stopped serving fresh option-chain snapshots.
- `REALTIME_FEED_STALE`
  Realtime packets are no longer arriving fast enough for trading use.
- `MARKET_FEED_DISCONNECTED`
  The websocket feed dropped and recovery has not finished yet.

## Fast remediation

1. If `slack_configured=false`, add `DHAN_P0_SLACK_WEBHOOK_URL` in Railway immediately.
2. If `totp_regeneration_enabled=false`, add `DHAN_PIN` and `DHAN_TOTP_SECRET` in Railway immediately.
3. If auth recovery still failed, generate a fresh Dhan access token manually.
4. Update Railway `DHAN_ACCESS_TOKEN`.
5. Redeploy the backend.
6. Re-check `/api/v1/market/provider-health`, `/api/v1/market/chain`, and the websocket feed.

## Railway commands

```bash
cd backend
railway variable list --json
railway variable set DHAN_ACCESS_TOKEN="<fresh token>"
railway redeploy
```

## Success criteria

- `p0_status` is `ok`
- `incident_open` is `false`
- `last_option_chain_success_at` is fresh
- `last_feed_message_at` is fresh during market hours
- `token_expires_at` is in the future
