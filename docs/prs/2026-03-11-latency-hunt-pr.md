# PR Title

`perf: move market data to live delta updates and cut render churn`

# PR Summary

## What changed

- replaced the backend's polling-only market freshness model with a live Dhan websocket feed for NIFTY spot and active-expiry option contracts
- batched quote deltas to the frontend at `150ms` instead of rebroadcasting the full chain
- scoped websocket portfolio refresh events to authorized portfolios
- stopped writing open-order mark updates to the database on every price move
- moved frontend quote handling to incremental patches
- updated positions/funds/analytics live from quote deltas
- reduced fallback polling intervals and removed repeated ATM auto-scroll
- updated the chart to reflect live spot ticks between candle fetches

## Why

The previous architecture had a hard freshness ceiling of roughly `5s` at the backend and compounded it with frontend polling plus broad rerenders. This PR moves the platform closer to production trading-terminal behavior by making price propagation event-driven and by cutting the amount of work done per tick on both the server and client.

## Quantified improvement

- freshness floor: `5000ms` -> `150ms` (`33.33x` faster)
- websocket payload: `51,183 bytes` full-chain event -> `412 bytes` single-quote delta (`99.20%` smaller)
- frontend row update scope: `81` rows -> `1` row (`98.77%` less row churn)

## Validation

- `python3 -m pytest`
- `npm run build`
- `npm run lint`
- `python3 backend/scripts/latency_benchmark.py`

## Notes

- live Dhan credentials were not present in this workspace, so live exchange-side timing was not measured in-session
- the benchmark numbers are from the synthetic payload model in `backend/scripts/latency_benchmark.py`
