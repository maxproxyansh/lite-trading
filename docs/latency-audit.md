# Latency Audit

## Scope

This pass focused on the live market-data path end to end:

1. Dhan ingestion on the backend.
2. WebSocket fan-out from the API.
3. Frontend state updates for quotes, positions, funds, and analytics.
4. Rendering cost in the options chain and chart.

## Before

The highest-impact latency bottlenecks were structural:

- Backend market data was capped by `market_poll_seconds=5`, because the app only refreshed Dhan's option-chain REST snapshot on a coarse loop.
- The backend rebroadcast the entire option chain instead of sending quote deltas.
- The frontend also polled `/market/chain` every 12s and portfolio views every 10s, so positions and funds lagged badly even after a new quote arrived.
- Most React components subscribed to the whole Zustand store, so a single tick triggered unrelated rerenders.
- `OptionsChain` called `scrollIntoView(..., behavior: 'smooth')` whenever the chain rows changed, which would become layout thrash once quote updates turned real-time.
- `process_open_orders_sync()` wrote `order.last_price` back to the database whenever the LTP moved, which is tolerable at 5s polling but not at sub-second tick frequency.

## After

### Backend

- Added a live Dhan market-feed path using `dhanhq.marketfeed.DhanFeed` and subscribed it to the active expiry contracts plus NIFTY spot.
- Batched websocket quote flushes to the frontend every `150ms` by default.
- Kept periodic REST option-chain refreshes for richer fields such as greeks/IV/OI integrity, but moved freshness onto the feed.
- Added portfolio-scoped websocket broadcast support so order-status refreshes can target only authorized clients.
- Changed open-order processing to run only for touched symbols and stopped persisting mere mark-to-market changes to SQLite on every tick.

### Frontend

- Added incremental `option.quotes` handling instead of replacing the full chain for every live update.
- Synced positions, funds, and analytics locally from quote deltas so mark-to-market values move with the feed.
- Reduced HTTP polling to fallback cadence:
  - shared market bootstrap: `30s`
  - portfolio views: `30s`
  - option chain snapshot fallback: `30s`
- Converted hot components to selector-based Zustand subscriptions.
- Memoized option-chain rows and limited updates to touched rows.
- Removed the repeated ATM auto-scroll by only centering once per expiry change.
- Wired live spot ticks into the visible chart so the chart advances between candle fetches.

## Quantified Delta

These numbers come from the benchmark script at [`backend/scripts/latency_benchmark.py`](/Users/proxy/trading/lite-latency/backend/scripts/latency_benchmark.py).

- Backend freshness floor:
  - before: `5000ms`
  - after: `150ms`
  - improvement: `33.33x` faster, `97.0%` lower worst-case waiting
- WebSocket payload size:
  - full chain event: `51,183 bytes`
  - single-quote delta: `412 bytes`
  - improvement: `99.20%` smaller
  - 10-quote delta: `3,039 bytes`
  - improvement: `94.06%` smaller
- Frontend render scope for a single-symbol move:
  - before: `81` rows reprocessed
  - after: `1` row patched
  - improvement: `98.77%` less row-level churn
- Portfolio freshness:
  - before: positions/funds/analytics could lag by `10s`
  - after: quote-driven mark-to-market is immediate on websocket delta arrival, with order-status refresh pushed by websocket and a `30s` fallback poll

## Validation

Executed successfully:

- `python3 -m pytest`
- `npm run build`
- `npm run lint`
- `python3 backend/scripts/latency_benchmark.py`

## Caveat

This workspace did not have live Dhan credentials configured during the audit, so the exchange-side latency was not measured against a live session. The quantified delta above is still meaningful because it measures the application's internal freshness floor, payload reduction, and render-scope reduction, which were the dominant bottlenecks in the codebase.
