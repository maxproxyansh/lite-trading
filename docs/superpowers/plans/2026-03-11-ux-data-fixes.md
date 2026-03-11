# UX Simplification & Data Pipeline Fixes

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix broken data pipeline and UX issues so the platform is actually usable for trading.

**Architecture:** Backend fixes to filter strikes around ATM, compute OI in lakhs, persist prev_close, and auto-advance expired expiries. Frontend fixes to change button colors to blue/orange, auto-scroll to ATM, remove broken TradingView symbols, and improve empty/disabled states.

**Tech Stack:** FastAPI backend, React 19 + Tailwind CSS v4 frontend, Dhan API for market data.

---

## Task 1: Backend — Filter strikes to ATM ± 20

**Files:**
- Modify: `backend/services/market_data.py:242-261`

**What:** Currently shows ALL strikes (18800-29200+). Filter to ATM ± 2000 points (~40 strikes at 50pt intervals).

- [ ] In `_fetch_option_chain()`, after line 238 (`atm = round(spot / 50) * 50 if spot else None`), add strike filtering:

```python
# After atm calculation, before the for loop:
strike_range = 2000  # ±2000 points from ATM
```

- [ ] Modify the for loop (line 242) to skip strikes outside range:

```python
for strike_key in sorted(raw_map.keys(), key=lambda item: float(item)):
    try:
        strike = int(float(strike_key))
    except (TypeError, ValueError):
        continue
    # Skip strikes far from ATM
    if atm and abs(strike - atm) > strike_range:
        continue
    # ... rest of loop unchanged
```

- [ ] Commit: `fix: filter option chain strikes to ATM ± 2000 points`

---

## Task 2: Backend — Compute oi_lakhs field

**Files:**
- Modify: `backend/services/market_data.py:314-332` (`_map_option_quote`)
- Modify: `backend/schemas.py:88-106` (`OptionQuote`)

**What:** Frontend expects `oi_lakhs` but backend only sends `oi` (raw number). Add computed field.

- [ ] In `_map_option_quote()`, after `"oi"` line (326), add:

```python
"oi_lakhs": round(float(oi_val) / 100000, 2) if (oi_val := self._safe_float(payload.get("oi") or payload.get("open_interest"))) is not None else None,
```

And update the existing oi line to use the same variable:

```python
"oi": oi_val if (oi_val := self._safe_float(payload.get("oi") or payload.get("open_interest"))) is not None else None,
```

Actually simpler — compute oi first, then derive oi_lakhs:

```python
raw_oi = self._safe_float(payload.get("oi") or payload.get("open_interest"))
```

Then in the return dict:
```python
"oi": raw_oi,
"oi_lakhs": round(raw_oi / 100000, 2) if raw_oi else None,
```

- [ ] In `schemas.py`, add `oi_lakhs` to `OptionQuote`:

```python
oi_lakhs: float | None = None
```

- [ ] Commit: `fix: compute oi_lakhs from raw OI for frontend display`

---

## Task 3: Backend — Persist prev_close and fix change calculation

**Files:**
- Modify: `backend/services/market_data.py:37-50` (MarketDataService.__init__)
- Modify: `backend/services/market_data.py:236-265`

**What:** When market closes, spot becomes 0 but prev_close should persist. Change should show last known values.

- [ ] Add persistent fields to `__init__`:

```python
self.last_known_spot: float = 0.0
self.last_known_prev_close: float = 0.0
self.last_known_change: float = 0.0
self.last_known_change_pct: float = 0.0
```

- [ ] In `_fetch_option_chain()`, fix the change calculation (around line 236-265):

```python
spot = float(body.get("last_price") or 0.0)
prev_close = float(body.get("prev_close") or body.get("previous_close") or 0.0)

# Persist known-good values
if spot > 0:
    self.last_known_spot = spot
if prev_close > 0:
    self.last_known_prev_close = prev_close

# Use last known values if current ones are zero (market closed)
effective_spot = spot if spot > 0 else self.last_known_spot
effective_prev = prev_close if prev_close > 0 else self.last_known_prev_close

change = round(effective_spot - effective_prev, 2) if effective_prev else self.last_known_change
change_pct = round((change / effective_prev) * 100, 2) if effective_prev else self.last_known_change_pct

if effective_spot > 0:
    self.last_known_change = change
    self.last_known_change_pct = change_pct
```

Then use `effective_spot` for the ATM calculation:

```python
atm = round(effective_spot / 50) * 50 if effective_spot else None
```

And in the returned snapshot, use `effective_spot`:

```python
"spot": effective_spot,
"change": change,
"change_pct": change_pct,
```

- [ ] Commit: `fix: persist prev_close and change values across market close`

---

## Task 4: Backend — Auto-advance expired expiry

**Files:**
- Modify: `backend/services/market_data.py:110-114`

**What:** If active_expiry date is in the past, auto-advance to next available expiry.

- [ ] After line 114, add date check:

```python
if self.active_expiry:
    try:
        expiry_date = datetime.strptime(self.active_expiry, "%Y-%m-%d").date()
        if expiry_date < date.today() and self.expiries:
            # Active expiry has passed, advance to next
            future_expiries = [e for e in self.expiries if e >= date.today().isoformat()]
            if future_expiries:
                self.active_expiry = future_expiries[0]
            elif self.expiries:
                self.active_expiry = self.expiries[0]
    except ValueError:
        pass
```

- [ ] Commit: `fix: auto-advance to next expiry when current one expires`

---

## Task 5: Frontend — Change BUY/SELL colors to blue/orange

**Files:**
- Modify: `frontend/src/styles/globals.css:30-33`
- Modify: `frontend/src/components/OrderTicket.tsx:74-77,191-192`
- Modify: `frontend/src/components/OrderModal.tsx` (buy/sell button colors)
- Modify: `frontend/src/components/OptionsChain.tsx` (B/S hover button colors)

**What:** BUY = #2962FF (blue), SELL = #FF6D00 (orange). Matches Zerodha Kite and user's Bubble app.

- [ ] In `globals.css`, update button colors:

```css
--color-btn-buy: #2962FF;
--color-btn-sell: #FF6D00;
--color-btn-buy-hover: #1b4ecf;
--color-btn-sell-hover: #e06000;
```

- [ ] In `OrderTicket.tsx`, change lines 75-77 from `bg-profit`/`bg-loss` to `bg-btn-buy`/`bg-btn-sell`:

```tsx
side === orderSide
  ? orderSide === 'BUY'
    ? 'bg-btn-buy text-white'
    : 'bg-btn-sell text-white'
```

And the submit button (line 191-192):
```tsx
side === 'BUY' ? 'bg-btn-buy' : 'bg-btn-sell'
```

- [ ] Same pattern in `OrderModal.tsx` — find buy/sell button color classes and replace `bg-profit`/`bg-loss` with `bg-btn-buy`/`bg-btn-sell`.

- [ ] In `OptionsChain.tsx`, the inline B/S hover buttons should also use `bg-btn-buy`/`bg-btn-sell` instead of `bg-profit`/`bg-loss`.

- [ ] Keep profit/loss colors GREEN/RED for P&L display (positions, analytics). Only BUY/SELL action buttons change to blue/orange.

- [ ] Commit: `feat: change BUY/SELL button colors to blue (#2962FF) / orange (#FF6D00)`

---

## Task 6: Frontend — Auto-scroll options chain to ATM

**Files:**
- Modify: `frontend/src/components/OptionsChain.tsx`

**What:** When chain loads, auto-scroll to the ATM row so users see relevant strikes immediately.

- [ ] Add a ref for the ATM row and scroll into view:

```tsx
import { useEffect, useRef } from 'react'

// Inside component:
const atmRef = useRef<HTMLTableRowElement>(null)

useEffect(() => {
  if (atmRef.current) {
    atmRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }
}, [chain?.rows])  // scroll when chain data changes
```

- [ ] On the ATM row's `<tr>`, add the ref:

```tsx
ref={row.is_atm ? atmRef : undefined}
```

- [ ] Commit: `feat: auto-scroll options chain to ATM strike on load`

---

## Task 7: Frontend — Remove broken TradingView ticker, improve empty states

**Files:**
- Modify: `frontend/src/components/TradingViewTickerTape.tsx`
- Modify: `frontend/src/components/NiftyChart.tsx`

**What:** Remove non-NSE symbols that show error icons. Improve "Market closed" message with trading hours.

- [ ] In `TradingViewTickerTape.tsx`, remove SPX and NDX (they show errors). Keep only:

```tsx
symbols: [
  { proName: "NSE:NIFTY", title: "NIFTY 50" },
  { proName: "NSE:BANKNIFTY", title: "BANK NIFTY" },
  { proName: "BSE:SENSEX", title: "SENSEX" },
  { proName: "NSE:INDIAVIX", title: "INDIA VIX" },
],
```

- [ ] In `NiftyChart.tsx`, improve the "Market closed" message (line 117-119):

```tsx
{candleCount === 0 && !loading && (
  <div className="absolute inset-0 flex flex-col items-center justify-center text-text-muted">
    <span className="text-sm">Market closed</span>
    <span className="text-xs mt-1">NSE trading hours: 9:15 AM – 3:30 PM IST</span>
  </div>
)}
```

- [ ] Commit: `fix: remove broken TradingView symbols, add market hours to chart`

---

## Task 8: Frontend — Improve OrderTicket clarity

**Files:**
- Modify: `frontend/src/components/OrderTicket.tsx`

**What:** Remove confusing "Contract type: --" display. Make disabled state clearer. Show "= X units" under lots.

- [ ] Remove "Contract type: --" line (line 85-87). Replace with nothing when no quote selected — the contract section already says "Select a contract".

- [ ] Add units display under lots input (after line 125):

```tsx
<div className="text-[10px] text-text-muted mt-0.5">= {lots * NIFTY_LOT_SIZE} units</div>
```

- [ ] Change disabled button opacity from `disabled:opacity-30` to `disabled:opacity-50` for better visibility.

- [ ] Change submit button text from `${side} ${optionType}` (which shows "BUY --") to just `${side}` when no quote, or full text when quote is selected:

```tsx
{loading ? 'Submitting...' : selectedQuote ? `${side} ${optionType}` : `${side}`}
```

- [ ] Commit: `fix: improve order ticket clarity and disabled states`

---

## Task 9: Frontend — Show LTP as "--" when 0.00 during market close

**Files:**
- Modify: `frontend/src/components/OptionsChain.tsx`

**What:** LTP 0.00 is confusing — looks like the option is worthless. Show "--" when market is closed and LTP is 0.

- [ ] Add a helper to format LTP:

```tsx
const formatLTP = (ltp: number) => {
  if (ltp === 0) return '--'
  return ltp.toFixed(2)
}
```

- [ ] Replace `{row.call.ltp.toFixed(2)}` and `{row.put.ltp.toFixed(2)}` with `{formatLTP(row.call.ltp)}` and `{formatLTP(row.put.ltp)}`.

- [ ] Commit: `fix: show "--" for zero LTP in options chain during market close`
