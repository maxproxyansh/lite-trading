# Lite - Complete Product & Technical Plan

> **Version:** 1.0 | **Date:** 2026-03-06 | **Author:** Max (AI Agent)
> **Status:** Ready for implementation

---

## Table of Contents

1. [Product Vision & Goals](#1-product-vision--goals)
2. [Full Feature List](#2-full-feature-list)
3. [Technical Architecture](#3-technical-architecture)
4. [UI/UX Specification](#4-uiux-specification)
5. [Data Flow](#5-data-flow)
6. [API Specification](#6-api-specification)
7. [Data Models & Database Schema](#7-data-models--database-schema)
8. [Development Phases](#8-development-phases)
9. [Environment Variables](#9-environment-variables)
10. [Directory Structure](#10-directory-structure)
11. [Open Questions & Decisions](#11-open-questions--decisions)

---

## 1. Product Vision & Goals

### What Is Lite?

Lite is a virtual options trading platform for Nifty 50 that looks and feels identical to Zerodha Kite. It uses **real live market data** from the Dhan API but executes trades in a virtual portfolio with virtual money. Both human traders and AI agents (like the signal engine at `/Users/proxy/trading/nifty_signals/`) can place and manage virtual positions.

### Problem It Solves

1. **No-risk strategy testing** - Test options strategies with real market conditions, zero financial risk.
2. **Agent performance tracking** - The signal engine generates signals; Lite lets us see exactly what P&L those signals would have produced if executed.
3. **Skill building** - Human traders can practice on a real-feel interface before risking capital.
4. **Agent-human comparison** - Side-by-side account performance: human decisions vs. agent signals.

### Why Not Just Use Zerodha's Paper Trading?

- Zerodha doesn't have a paper trading mode
- No API access for agent-placed trades
- No custom signal overlay
- No way to compare human vs. agent accounts
- No confidence score / signal metadata tracking

### Success Metrics

- Agent account win rate > 55% over 30 trading days
- Human account can place and close a full options trade in < 30 seconds
- Options chain LTP refreshes within 1 second of Dhan tick
- Zero crashes during market hours
- P&L accuracy: virtual P&L within ₹1 of manually calculated P&L

### Users

1. **Ansh (human trader)** - Places trades manually, reviews signal recommendations, monitors portfolio
2. **Signal Engine (AI agent)** - Calls REST API to place virtual trades when signals fire with confidence > threshold
3. **Future agents** - Any AI system with an API key can trade on Lite

---

## 2. Full Feature List

### 2.1 Dashboard / Main View

- **Header bar** (always visible):
  - Lite logo (left)
  - LIVE indicator (green pulsing dot)
  - Nifty 50 LTP (large, live updating)
  - Nifty change (absolute + %)
  - VIX value
  - PCR value (from signal engine or computed)
  - Virtual Balance (account selector dropdown: "Human" / "Agent")
  - Today's P&L (color: green if positive, red if negative)
  - Open Positions count
  - Win Rate %
  - Market status badge (OPEN / CLOSED / PRE-OPEN)

- **Left sidebar** (icon-only, like Kite):
  - Dashboard icon (active)
  - Positions icon
  - Orders icon
  - History icon
  - Analytics icon
  - Settings icon (bottom)

- **Main area** - chart + options chain
- **Right panel** - tabbed: Trade | Positions | History

### 2.2 Chart Panel

- **Instrument selector**: Fixed to "NIFTY 50" (no need to change for now)
- **Timeframe pills**: 1m | 5m | 15m (default) | 1h | D
- **Chart type**: Candlestick (default), Line toggle
- **Overlays**: EMA 9 (white), EMA 21 (blue) - toggleable
- **Signal markers**: Vertical orange arrow markers where signal engine fired (▲ for bullish, ▼ for bearish), with tooltip showing signal details on hover
- **Price line**: Horizontal dashed line at current LTP
- **Volume bars** at bottom (optional, can be Phase 2)
- **Library**: `lightweight-charts` v4 by TradingView (same lib Kite uses)
- **Data source**: OHLCV candles from Dhan Historical Data API

### 2.3 Options Chain Panel

- **Header**: "OPTIONS CHAIN" label | Expiry selector dropdown (default: nearest weekly expiry) | "SPOT: ₹XX,XXX.XX" (right-aligned)
- **Columns** (left to right):
  - OI (L) - Calls OI in lakhs
  - IV% - Call IV
  - LTP - Call LTP (green color, right-aligned)
  - STRIKE - Strike price (center, ATM highlighted in orange #FF6B35 bg)
  - LTP - Put LTP (red color)
  - IV% - Put IV
  - OI (L) - Put OI
  - [OI bar visual] - horizontal bar behind OI numbers showing relative OI magnitude
- **Rows**: 8 strikes above ATM, ATM, 8 strikes below ATM (17 rows total)
- **Click on LTP**: Auto-fills the trade panel on the right (CE click -> fills CE buy, PE click -> fills PE buy)
- **Refresh**: Every 5 seconds via Dhan option chain API polling
- **ATM detection**: Nearest strike to current Nifty spot

### 2.4 Trade Panel (Right Panel, Tab 1: "Trade")

- **Latest Signal box** (top of panel, collapsible):
  - Signal direction badge: BEARISH (red) / BULLISH (green) / NEUTRAL (gray)
  - Timestamp of signal
  - Confidence score badge (e.g., "66% confidence")
  - Recommended instrument (e.g., "BUY 24300 PE")
  - Entry range, Target, Stop Loss
  - "LOAD SIGNAL" button -> auto-fills trade form below

- **Trade form**:
  - Instrument toggle: CE | PE (pill buttons)
  - Strike price dropdown (pre-selected from chain click or signal load)
  - Expiry dropdown
  - Order type: MARKET (only for virtual - simplifies execution)
  - Lots field (default: 1) - shows qty = lots × 25
  - Market LTP display (live updating)
  - IV% and IV label (Low / Moderate / High)
  - Estimated Cost (LTP × qty)
  - Target exit display (from signal, editable)
  - Stop loss display (from signal, editable)
  - **BUY VIRTUAL** button (green, full width, shows cost)
  - Account selector: Human | Agent (which virtual account places the trade)

### 2.5 Positions Panel (Right Panel, Tab 2: "Positions")

- List of all open positions for selected account
- Each position card shows:
  - Strike + type (e.g., "24200 PE")
  - Entry price
  - Current LTP (live updating)
  - Qty (lots × 25)
  - Unrealized P&L (color coded)
  - Stop loss level
  - Target level
  - Progress bar: stop ->-> LTP ->-> target (shows where price is between stop and target)
  - **CLOSE** button (closes at current LTP)
- Summary row: Total unrealized P&L

### 2.6 History Panel (Right Panel, Tab 3: "History")

- List of closed trades (most recent first)
- Each row: date/time | instrument | buy price | exit price | qty | P&L | outcome (WIN/LOSS badge)
- Pagination (10 per page)

### 2.7 Positions Page (Full page, left nav)

- Expanded view of Positions panel
- Both Human and Agent accounts shown side by side (two columns)
- Sortable by P&L, entry time, instrument

### 2.8 Orders Page (Full page, left nav)

- All orders placed (market orders = immediately filled for virtual)
- Shows: order time, instrument, type (BUY), qty, fill price, status (FILLED / REJECTED)
- REJECTED status if: market closed, insufficient balance, invalid instrument

### 2.9 History / Trade Log Page (Full page, left nav)

- Complete trade history for both accounts
- Filters: date range, account (human/agent/both), outcome (win/loss/all)
- Export as CSV button

### 2.10 Analytics Page (Full page, left nav)

- **Account switcher**: Human | Agent | Combined
- **Stats cards** (top row):
  - Total Trades
  - Win Rate %
  - Average P&L per trade
  - Best trade
  - Worst trade
  - Total P&L (all time)
  - Current drawdown %
- **Equity curve chart**: Cumulative P&L over time (line chart, lightweight-charts)
- **P&L by day**: Bar chart (green = profit day, red = loss day)
- **Win/Loss ratio**: Donut chart
- **Signal accuracy**: If trade was agent-placed, show signal confidence vs. actual outcome correlation
- **Average holding time**: Mean duration of closed trades

### 2.11 Settings Page (Left nav, bottom icon)

- Virtual account management:
  - Human account: reset balance to ₹5,00,000
  - Agent account: reset balance to ₹5,00,000
- Dhan API key display (masked) + test connection button
- Signal engine connection: shows last signal time + connection status
- Theme: Dark only (no toggle needed)

### 2.12 Virtual Account System

- Two accounts by default:
  - **human** (id: `human`) - operated via UI
  - **agent** (id: `agent`) - operated via REST API by signal engine
- Each account has:
  - Starting balance: ₹5,00,000
  - Current cash balance (reduces on buy, increases on sell)
  - Open positions (with unrealized P&L)
  - Closed trade history
  - Running statistics
- Margin calculation: options are cash-settled, cost = LTP × lot size × lots
- No leverage - full premium paid upfront

### 2.13 Agent API

- Any system with a valid `X-API-Key` header can:
  - Place virtual trades
  - Get current positions
  - Get account balance
  - Get latest signals
  - Close positions
- The existing signal engine (`/Users/proxy/trading/nifty_signals/main.py`) will be modified to call POST `/api/trade` after generating a signal (when confidence > 60)

---

## 3. Technical Architecture

### Stack Decisions

| Layer | Technology | Reason |
|-------|-----------|--------|
| Frontend | React 18 + Vite | Fast dev, same ecosystem as mission-control |
| Styling | Tailwind CSS + CSS variables | Kite color tokens, fast iteration |
| Charts | lightweight-charts v4 (TradingView) | Same lib as Kite, best performance |
| Backend | Python FastAPI | Existing signal engine is Python, easy integration |
| Database | SQLite (via SQLAlchemy) | Simple, no infra needed, sufficient for this scale |
| Live prices | Dhan WebSocket API | Already authenticated, < 1s latency |
| Historical candles | Dhan Historical Data API | OHLCV for chart |
| Option chain | Dhan Option Chain API | Polled every 5s |
| Hosting | Local (localhost:5173 frontend, localhost:8000 backend) | Dev + personal use |

### Backend Structure

FastAPI app with the following routers:
- `/api/market` - live prices, option chain, candles
- `/api/trade` - place/close virtual trades
- `/api/positions` - get open positions
- `/api/orders` - order history
- `/api/account` - balance, stats
- `/api/signals` - latest signals (reads from signal engine output)
- `/api/ws` - WebSocket endpoint for frontend to receive live price updates

### WebSocket Architecture

```
Dhan WebSocket -> Python backend (dhan_ws.py) -> broadcasts to frontend via FastAPI WebSocket
```

- Backend connects to Dhan WebSocket, subscribes to NIFTY 50 index feed
- Backend maintains a dict of `{symbol: last_ltp}` in memory
- Frontend connects to `ws://localhost:8000/api/ws`
- Backend pushes price updates to all connected frontend clients
- Also pushes option chain snapshot every 5s

### Virtual Order Matching

- Order type: MARKET only
- Fill price = current LTP at time of order submission
- Immediate fill (no order book simulation)
- Validation checks:
  1. Market open? (9:15 AM – 3:30 PM IST, Mon-Fri) - if closed, REJECT with message
  2. Sufficient balance? - if not, REJECT
  3. Valid instrument? (must exist in current option chain) - if not, REJECT
- On fill: deduct `ltp × qty` from account balance, create Position record

### Integration with Signal Engine

Signal engine (`/Users/proxy/trading/nifty_signals/main.py`) currently writes signals to a JSON file. We will:
1. Add a Lite client to signal engine that calls `POST /api/trade` after generating a signal
2. Uses `account_id=agent` and `X-API-Key` from env var
3. Configurable: `NIFTYDESK_AUTO_TRADE=true/false` and `NIFTYDESK_MIN_CONFIDENCE=60`

---

## 4. UI/UX Specification

### Color Tokens (Kite-exact)

```css
:root {
  /* Backgrounds */
  --bg-primary: #1B1B1B;        /* main app background */
  --bg-secondary: #2B2B2B;      /* cards, panels */
  --bg-tertiary: #363636;       /* table rows hover, input bg */
  --bg-sidebar: #1B1B1B;        /* left sidebar */
  --bg-header: #1B1B1B;         /* top header */
  
  /* Borders */
  --border-primary: #363636;
  --border-secondary: #404040;
  
  /* Text */
  --text-primary: #EEEEEE;      /* main text */
  --text-secondary: #9B9B9B;    /* labels, secondary */
  --text-muted: #636363;        /* disabled, placeholders */
  
  /* Semantic */
  --color-profit: #1DB954;      /* Kite green */
  --color-loss: #E84040;        /* Kite red */
  --color-signal: #FF6B35;      /* Lite signal orange */
  --color-atm: #FF6B35;         /* ATM strike highlight */
  --color-neutral: #9B9B9B;
  
  /* Interactive */
  --btn-buy: #1DB954;
  --btn-sell: #E84040;
  --btn-buy-hover: #18A448;
  
  /* Chart */
  --candle-bull: #1DB954;
  --candle-bear: #E84040;
  --ema-9: rgba(255,255,255,0.7);
  --ema-21: rgba(100,180,255,0.7);
}
```

### Typography

```css
font-family: 'Inter', -apple-system, sans-serif;
/* Sizes */
--text-xs: 11px;    /* table cells, labels */
--text-sm: 12px;    /* secondary text */
--text-base: 13px;  /* default body */
--text-lg: 14px;    /* section headers */
--text-xl: 16px;    /* card titles */
--text-2xl: 20px;   /* Nifty LTP */
--text-3xl: 24px;   /* big numbers in header */
```

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER BAR (48px height)                                     │
├────┬────────────────────────────────────────┬───────────────┤
│    │  MAIN AREA                             │ RIGHT PANEL   │
│    │  ┌──────────────────────────────────┐  │ (320px fixed) │
│ S  │  │  CHART (flexible height ~350px)  │  │               │
│ I  │  └──────────────────────────────────┘  │ [Trade tab]   │
│ D  │  ┌──────────────────────────────────┐  │ [Pos tab]     │
│ E  │  │  OPTIONS CHAIN (remaining height)│  │ [History tab] │
│    │  └──────────────────────────────────┘  │               │
│(48)│                                        │               │
└────┴────────────────────────────────────────┴───────────────┘
```

- Sidebar: 48px wide, icons only, `position: fixed`, `height: 100vh`
- Header: 48px tall, `position: fixed`, `width: 100%`, `z-index: 100`
- Main content: `margin-left: 48px`, `margin-top: 48px`, `height: calc(100vh - 48px)`
- Right panel: `width: 320px`, `position: fixed`, `right: 0`, `top: 48px`, `height: calc(100vh - 48px)`, `overflow-y: auto`
- Main area: `margin-right: 320px`, splits vertically between chart (40%) and chain (60%)

### Components

#### Header Component (`<Header />`)
Props: none (reads from global state)
- Left: Logo text "Lite" (weight 700, white) + green dot + "LIVE" badge
- Center: `<NiftyPrice />` -> LTP in large text, change in small text below
- Stats row (right of center): VIX | PCR | separator | Virtual Balance | Today P&L | Positions | Win Rate
- Account selector: dropdown `<select>` showing "Human ₹X,XX,XXX" / "Agent ₹X,XX,XXX"

#### Chart Component (`<NiftyChart />`)
- Uses `createChart()` from `lightweight-charts`
- `ISeriesApi<'Candlestick'>` for candles
- `ISeriesApi<'Line'>` × 2 for EMAs
- `ISeriesApi<'Line'>` with markers for signals (use `setMarkers()`)
- Timeframe buttons call `fetchCandles(timeframe)` -> updates chart data
- Chart auto-resizes on window resize (ResizeObserver)
- Loading state: spinner overlay on chart area
- Error state: "Failed to load chart data" message with retry button

#### OptionsChain Component (`<OptionsChain />`)
- `<table>` with CSS `table-layout: fixed`
- Expiry dropdown at top; on change -> refetch chain
- OI bars: `<div>` with `width: {oi/maxOI * 100}%`, color green (calls) / red (puts)
- ATM row: `background: rgba(255,107,53,0.15)`, strike cell gets orange badge
- Row click handler: `onStrikeSelect(strike, type)` -> updates trade panel
- Loading: skeleton rows (pulsing gray bars)
- Polling: `setInterval(fetchChain, 5000)` with cleanup on unmount

#### TradePanel Component (`<TradePanel />`)
- **Signal box**: Shown only if signal exists and is < 4 hours old
  - Dismissible (X button, stores dismissed signal id in state)
  - "LOAD SIGNAL" button: calls `loadSignal(signal)` -> sets form state
- **Form state** (React `useState`):
  - `instrument`: 'CE' | 'PE'
  - `strike`: number
  - `expiry`: string (YYYY-MM-DD)
  - `lots`: number (min 1, max 50)
  - `targetPrice`: number (editable)
  - `stopLoss`: number (editable)
- **Live LTP**: subscribes to WebSocket, updates `currentLtp` when matching instrument changes
- **BUY VIRTUAL button**:
  - onClick: `POST /api/trade` with form data
  - Loading state: button shows spinner, disabled
  - Success: toast "Position opened at ₹XX", switch to Positions tab
  - Error: toast with error message (red)

#### PositionCard Component (`<PositionCard />`)
Props: `position: Position`
- Live LTP: subscribes to WebSocket for this specific instrument
- P&L: `(currentLtp - entryPrice) × qty` (recalculated client-side from WS updates)
- Progress bar: CSS `background: linear-gradient` from stop (red) to target (green), indicator at current price % position
- CLOSE button: `DELETE /api/positions/{id}` -> fills at current LTP

### Loading States
- Chart: Full overlay spinner (semi-transparent black bg)
- Options chain: 10 skeleton rows
- Positions: "Loading positions..." text
- Header stats: "-" until first WS message received

### Error States
- WS disconnected: yellow banner "Live feed disconnected - retrying..." (auto-reconnects every 5s)
- Market closed: Trade panel shows "Market Closed" badge, BUY button disabled
- API error: Toast notification bottom-right, auto-dismisses after 5s

---

## 5. Data Flow

### 5.1 Live Price Updates

```
Dhan WS (market data) 
  -> backend/dhan_ws.py (WebSocket client)
    -> parses LTP for Nifty 50 index + all option chain instruments
    -> updates in-memory price dict: prices["NIFTY50"] = 24198.20
    -> broadcasts to all connected frontend WebSocket clients
      -> frontend receives: { type: "price_update", symbol: "NIFTY50", ltp: 24198.20 }
      -> React state update -> header LTP re-renders
      -> open position cards recalculate P&L
```

### 5.2 Option Chain Refresh

```
Frontend: setInterval(fetchChain, 5000)
  -> GET /api/market/chain?expiry=2026-03-06
    -> backend calls Dhan Option Chain API
    -> parses CE/PE data for all strikes
    -> returns structured JSON
  -> Frontend updates options chain table
```

### 5.3 Human Trade Execution (end-to-end)

```
1. User clicks "24300 PE" LTP cell in options chain
   -> TradePanel: setInstrument('PE'), setStrike(24300)

2. User clicks "BUY VIRTUAL"
   -> Frontend: POST /api/trade { account_id: "human", instrument: "PE", strike: 24300, expiry: "2026-03-06", lots: 1, target_price: 228, stop_loss: 98 }

3. Backend validates:
   a. Market open? -> check current IST time
   b. Account balance >= ltp * 25 * lots?
   c. Instrument exists in chain?

4. If valid:
   a. Fetch current LTP from prices dict
   b. Create Order record (status=FILLED, fill_price=ltp)
   c. Create Position record (entry_price=ltp, qty=25*lots, target=228, stop=98)
   d. Deduct cost from account balance
   e. Return { success: true, position: {...} }

5. Frontend:
   a. Shows success toast
   b. Switches to Positions tab
   c. New position card appears
   d. Header balance updates
```

### 5.4 Agent Trade Execution

```
1. Signal engine generates signal (confidence: 66%)
2. signal engine calls: POST /api/trade
   Headers: { X-API-Key: "agent-secret-key" }
   Body: { account_id: "agent", instrument: "PE", strike: 24300, expiry: "2026-03-06", lots: 1, target_price: 228, stop_loss: 98, signal_id: "uuid", confidence: 66 }
3. Backend: same validation as human trade
4. Position created with signal_id linked for analytics
5. Response: { success: true, position_id: "uuid" }
6. Signal engine logs: "Virtual trade placed: position_id=..."
```

### 5.5 Position Close

```
1. User clicks CLOSE on position card (or agent calls DELETE /api/positions/{id})
2. Backend:
   a. Fetch current LTP
   b. Calculate P&L: (exit_ltp - entry_price) × qty
   c. Update position: status=CLOSED, exit_price=ltp, pnl=calculated
   d. Create closed trade record
   e. Add P&L back to account balance
   f. Update account statistics (win_rate, total_pnl, etc.)
3. Frontend:
   a. Position card disappears from open positions
   b. Appears in History tab
   c. Header P&L updates
```

---

## 6. API Specification

Base URL: `http://localhost:8000`
Auth for agent endpoints: `X-API-Key: {NIFTYDESK_AGENT_KEY}` header
Human UI calls: no auth (localhost only)

### Market Data Endpoints

#### GET /api/market/snapshot
Returns current Nifty LTP, VIX, PCR.
```json
{
  "nifty_ltp": 24198.20,
  "nifty_change": -226.35,
  "nifty_change_pct": -0.93,
  "vix": 14.82,
  "pcr": 1.24,
  "market_status": "OPEN",
  "timestamp": "2026-03-06T09:45:00Z"
}
```

#### GET /api/market/chain?expiry=YYYY-MM-DD
Returns option chain for given expiry.
```json
{
  "spot": 24198.20,
  "expiry": "2026-03-06",
  "strikes": [
    {
      "strike": 24300,
      "is_atm": true,
      "ce": { "ltp": 54.70, "iv": 9.9, "oi_lakhs": 22.3 },
      "pe": { "ltp": 142.80, "iv": 10.8, "oi_lakhs": 38.6 }
    }
  ]
}
```

#### GET /api/market/candles?timeframe=15m
Returns OHLCV candles for Nifty 50.
```json
{
  "timeframe": "15m",
  "candles": [
    { "time": 1741234800, "open": 24350, "high": 24380, "low": 24300, "close": 24320, "volume": 123456 }
  ]
}
```

#### GET /api/market/expiries
Returns list of available option expiry dates.
```json
{ "expiries": ["2026-03-06", "2026-03-13", "2026-03-27", "2026-04-24"] }
```

### Trading Endpoints

#### POST /api/trade
Place a virtual trade.
```json
// Request
{
  "account_id": "human",          // "human" | "agent"
  "instrument": "PE",             // "CE" | "PE"
  "strike": 24300,
  "expiry": "2026-03-06",
  "lots": 1,
  "target_price": 228.0,          // optional
  "stop_loss": 98.0,              // optional
  "signal_id": "uuid",            // optional, links to signal record
  "confidence": 66                // optional, signal confidence %
}
// Response (success)
{
  "success": true,
  "order_id": "uuid",
  "position_id": "uuid",
  "fill_price": 142.80,
  "qty": 25,
  "cost": 3570.0,
  "account_balance_after": 496430.0
}
// Response (error)
{
  "success": false,
  "error": "MARKET_CLOSED" | "INSUFFICIENT_BALANCE" | "INVALID_INSTRUMENT"
}
```

#### DELETE /api/positions/{position_id}
Close a position at current market price.
```json
// Response
{
  "success": true,
  "exit_price": 185.50,
  "pnl": 1067.50,
  "account_balance_after": 501497.50
}
```

### Account Endpoints

#### GET /api/account/{account_id}
```json
{
  "account_id": "human",
  "starting_balance": 500000.0,
  "current_balance": 496430.0,
  "total_pnl": -3570.0,
  "today_pnl": 3240.0,
  "open_positions": 2,
  "total_trades": 47,
  "win_rate": 67.0,
  "avg_pnl_per_trade": 425.50
}
```

#### GET /api/account/{account_id}/positions
Returns all open positions.
```json
{
  "positions": [
    {
      "id": "uuid",
      "instrument": "PE",
      "strike": 24200,
      "expiry": "2026-03-06",
      "entry_price": 62.40,
      "current_ltp": 88.60,
      "qty": 25,
      "unrealized_pnl": 655.0,
      "target_price": 122.0,
      "stop_loss": 43.0,
      "opened_at": "2026-03-06T09:32:00Z"
    }
  ]
}
```

#### GET /api/account/{account_id}/history?limit=50&offset=0
```json
{
  "trades": [
    {
      "id": "uuid",
      "instrument": "CE",
      "strike": 24400,
      "entry_price": 45.60,
      "exit_price": 29.30,
      "qty": 25,
      "pnl": -407.50,
      "outcome": "LOSS",
      "opened_at": "2026-03-05T10:15:00Z",
      "closed_at": "2026-03-05T14:22:00Z",
      "signal_id": "uuid",
      "confidence": 66
    }
  ],
  "total": 47,
  "page_size": 50,
  "offset": 0
}
```

### Signal Endpoints

#### GET /api/signals/latest
Returns the latest signal from the signal engine.
```json
{
  "id": "uuid",
  "direction": "BEARISH",
  "confidence": 66,
  "instrument": "PE",
  "strike": 24300,
  "expiry": "2026-03-06",
  "entry_low": 138.0,
  "entry_high": 162.0,
  "target": 228.0,
  "stop_loss": 98.0,
  "generated_at": "2026-03-06T13:00:00Z",
  "signal_data": { ... }  // full signal engine output
}
```

#### GET /api/signals?limit=20
Returns last N signals.

### WebSocket

#### WS /api/ws
Frontend connects here to receive live updates.

Messages sent from server:
```json
// Price update
{ "type": "price_update", "symbol": "NIFTY50", "ltp": 24198.20, "change": -226.35 }

// Option LTP update (for open positions)
{ "type": "option_ltp", "strike": 24200, "instrument": "PE", "expiry": "2026-03-06", "ltp": 88.60 }

// Market status change
{ "type": "market_status", "status": "OPEN" }

// New signal
{ "type": "new_signal", "signal": { ... } }

// Position update (after auto-stop or auto-target hit - Phase 2 feature)
{ "type": "position_closed", "position_id": "uuid", "reason": "TARGET_HIT", "pnl": 1067.50 }
```

---

## 7. Data Models & Database Schema

Using SQLAlchemy with SQLite. DB file: `/Users/proxy/trading/niftydesk/data/niftydesk.db`

### accounts table
```sql
CREATE TABLE accounts (
  id TEXT PRIMARY KEY,              -- "human" | "agent"
  display_name TEXT NOT NULL,
  starting_balance REAL NOT NULL DEFAULT 500000.0,
  current_balance REAL NOT NULL DEFAULT 500000.0,
  total_pnl REAL NOT NULL DEFAULT 0.0,
  today_pnl REAL NOT NULL DEFAULT 0.0,
  total_trades INTEGER NOT NULL DEFAULT 0,
  winning_trades INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed data
INSERT INTO accounts VALUES ('human', 'Human Trader', 500000, 500000, 0, 0, 0, 0, NOW(), NOW());
INSERT INTO accounts VALUES ('agent', 'Signal Agent', 500000, 500000, 0, 0, 0, 0, NOW(), NOW());
```

### orders table
```sql
CREATE TABLE orders (
  id TEXT PRIMARY KEY,              -- UUID
  account_id TEXT NOT NULL,
  instrument TEXT NOT NULL,         -- "CE" | "PE"
  strike INTEGER NOT NULL,
  expiry TEXT NOT NULL,             -- "YYYY-MM-DD"
  order_type TEXT NOT NULL DEFAULT 'MARKET',
  lots INTEGER NOT NULL,
  qty INTEGER NOT NULL,             -- lots * 25
  requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  fill_price REAL,
  filled_at TIMESTAMP,
  status TEXT NOT NULL,             -- "FILLED" | "REJECTED"
  reject_reason TEXT,
  signal_id TEXT,
  FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### positions table
```sql
CREATE TABLE positions (
  id TEXT PRIMARY KEY,              -- UUID
  account_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  instrument TEXT NOT NULL,         -- "CE" | "PE"
  strike INTEGER NOT NULL,
  expiry TEXT NOT NULL,
  entry_price REAL NOT NULL,
  qty INTEGER NOT NULL,
  target_price REAL,
  stop_loss REAL,
  status TEXT NOT NULL DEFAULT 'OPEN',  -- "OPEN" | "CLOSED"
  exit_price REAL,
  realized_pnl REAL,
  exit_reason TEXT,                 -- "MANUAL" | "TARGET_HIT" | "STOP_HIT"
  opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  closed_at TIMESTAMP,
  signal_id TEXT,
  confidence INTEGER,
  FOREIGN KEY (account_id) REFERENCES accounts(id),
  FOREIGN KEY (order_id) REFERENCES orders(id)
);
```

### signals table
```sql
CREATE TABLE signals (
  id TEXT PRIMARY KEY,              -- UUID
  direction TEXT NOT NULL,          -- "BULLISH" | "BEARISH" | "NEUTRAL"
  confidence INTEGER NOT NULL,
  instrument TEXT,                  -- "CE" | "PE"
  strike INTEGER,
  expiry TEXT,
  entry_low REAL,
  entry_high REAL,
  target REAL,
  stop_loss REAL,
  nifty_ltp REAL,
  vix REAL,
  pcr REAL,
  raw_data TEXT,                    -- JSON string of full signal engine output
  generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### daily_stats table
(For analytics - updated at end of each trading day)
```sql
CREATE TABLE daily_stats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id TEXT NOT NULL,
  date TEXT NOT NULL,               -- "YYYY-MM-DD"
  opening_balance REAL,
  closing_balance REAL,
  day_pnl REAL,
  trades_count INTEGER,
  wins INTEGER,
  losses INTEGER,
  UNIQUE(account_id, date),
  FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

---

## 8. Development Phases

### Phase 1: Static UI (Day 1)
**Goal**: Pixel-perfect Kite clone running in browser with mock data

Tasks:
- [ ] Setup Vite + React + Tailwind project
- [ ] Define all CSS color tokens (Kite palette)
- [ ] Build Header component with mock Nifty data
- [ ] Build Sidebar component (icon-only nav)
- [ ] Integrate lightweight-charts with mock candle data
- [ ] Build OptionsChain component with mock data (10 strikes)
- [ ] Build TradePanel with signal box + trade form (no submission)
- [ ] Build PositionCard components with mock positions
- [ ] Build History tab with mock data
- [ ] Wire up React Router for page navigation
- [ ] Build Analytics page with mock charts

Deliverable: `npm run dev` -> fully styled Kite-clone UI at localhost:5173

### Phase 2: Backend + Live Data (Days 2-3)
**Goal**: Real Dhan data flowing through

Tasks:
- [ ] Setup FastAPI project with SQLAlchemy + SQLite
- [ ] Seed accounts table with human + agent accounts
- [ ] Implement `dhan_ws.py` - Dhan WebSocket client that maintains price dict
- [ ] Implement `/api/market/snapshot` using prices dict
- [ ] Implement `/api/market/chain` using Dhan option chain API
- [ ] Implement `/api/market/candles` using Dhan historical API
- [ ] Implement `/api/ws` FastAPI WebSocket that streams price updates
- [ ] Wire frontend: Header subscribes to WS -> live Nifty LTP
- [ ] Wire frontend: OptionsChain polls `/api/market/chain` every 5s
- [ ] Wire frontend: Chart fetches candles on timeframe change

Deliverable: Dashboard shows live Nifty LTP, real option chain, real chart

### Phase 3: Virtual Trading Engine (Days 3-4)
**Goal**: Full trade lifecycle working

Tasks:
- [ ] Implement `POST /api/trade` with validation + order fill
- [ ] Implement `DELETE /api/positions/{id}` close
- [ ] Implement `GET /api/account/{id}` stats
- [ ] Implement `GET /api/account/{id}/positions`
- [ ] Implement `GET /api/account/{id}/history`
- [ ] Wire TradePanel BUY VIRTUAL button to API
- [ ] Wire PositionCard CLOSE button to API
- [ ] Update account balance in real-time via WS after trades
- [ ] Handle market closed validation
- [ ] Ensure P&L in position cards updates live from WS

Deliverable: Full trade flow works - buy, hold, close, see P&L

### Phase 4: Agent API + Signal Integration (Day 5)
**Goal**: Signal engine can auto-trade on Lite

Tasks:
- [ ] Implement API key auth middleware (`X-API-Key` header check)
- [ ] Implement `GET /api/signals/latest`
- [ ] Implement `GET /api/signals` list endpoint
- [ ] Add signal ingestion: either file-watch on signal engine output or signal engine calls `POST /api/signals`
- [ ] Modify signal engine (`/Users/proxy/trading/nifty_signals/main.py`):
  - Add `niftydesk_client.py` module
  - After signal generated, if `NIFTYDESK_AUTO_TRADE=true` and `confidence >= NIFTYDESK_MIN_CONFIDENCE`, call `POST /api/trade` with `account_id=agent`
- [ ] Show latest signal in TradePanel signal box (polling or WS push)
- [ ] Show "Agent" account in UI header with live balance

Deliverable: Signal engine fires -> virtual trade appears in agent account automatically

### Phase 5: Analytics + Polish (Days 6-7)
**Goal**: Full analytics + production-ready feel

Tasks:
- [ ] Build Analytics page: equity curve, P&L by day, win/loss donut
- [ ] Build daily_stats computation (cron or on-close trigger)
- [ ] Add export to CSV on History page
- [ ] Add account reset functionality in Settings
- [ ] Add toast notification system
- [ ] Error boundary + loading states everywhere
- [ ] Auto-reconnect WebSocket with backoff
- [ ] Position auto-close when target or stop is hit (backend: check on each WS price update)
- [ ] README.md with setup + run instructions

Deliverable: Complete, polished, production-ready Lite

---

## 9. Environment Variables

Backend `.env` (at `/Users/proxy/trading/niftydesk/backend/.env`):
```bash
# Dhan API (already configured for signal engine)
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token

# Lite
NIFTYDESK_AGENT_KEY=niftydesk-agent-secret-2026   # API key for agent access
NIFTYDESK_DB_PATH=/Users/proxy/trading/niftydesk/data/niftydesk.db
NIFTYDESK_HOST=0.0.0.0
NIFTYDESK_PORT=8000
```

Signal Engine additions (to `/Users/proxy/trading/nifty_signals/.env`):
```bash
NIFTYDESK_URL=http://localhost:8000
NIFTYDESK_API_KEY=niftydesk-agent-secret-2026
NIFTYDESK_AUTO_TRADE=true
NIFTYDESK_MIN_CONFIDENCE=60
```

---

## 10. Directory Structure

```
/Users/proxy/trading/niftydesk/
├── PLAN.md                         # This document
├── README.md                       # Setup + run instructions
├── data/
│   └── niftydesk.db               # SQLite database (auto-created)
│
├── backend/
│   ├── .env
│   ├── requirements.txt
│   ├── main.py                     # FastAPI app entry point
│   ├── database.py                 # SQLAlchemy setup, session factory
│   ├── models.py                   # SQLAlchemy ORM models
│   ├── schemas.py                  # Pydantic request/response schemas
│   ├── auth.py                     # API key validation middleware
│   ├── dhan_ws.py                  # Dhan WebSocket client (price feed)
│   ├── market_hours.py             # IST market open/close logic
│   ├── routers/
│   │   ├── market.py               # /api/market/* endpoints
│   │   ├── trade.py                # /api/trade endpoint
│   │   ├── positions.py            # /api/positions/* endpoints
│   │   ├── account.py              # /api/account/* endpoints
│   │   ├── signals.py              # /api/signals/* endpoints
│   │   └── websocket.py            # /api/ws WebSocket endpoint
│   └── services/
│       ├── trade_service.py        # Virtual order matching logic
│       ├── account_service.py      # Balance + stats management
│       └── signal_service.py       # Signal ingestion + storage
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── tailwind.config.js
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                 # Router setup
│       ├── styles/
│       │   ├── globals.css         # CSS variables (color tokens)
│       │   └── kite.css            # Kite-specific overrides
│       ├── store/
│       │   └── useStore.ts         # Zustand global state (prices, account, ws)
│       ├── hooks/
│       │   ├── useWebSocket.ts     # WS connection + reconnect
│       │   ├── useOptionChain.ts   # Polling option chain
│       │   └── useAccount.ts       # Account data fetching
│       ├── components/
│       │   ├── Header.tsx
│       │   ├── Sidebar.tsx
│       │   ├── NiftyChart.tsx
│       │   ├── OptionsChain.tsx
│       │   ├── TradePanel.tsx
│       │   ├── SignalBox.tsx
│       │   ├── PositionCard.tsx
│       │   ├── Toast.tsx
│       │   └── LoadingSpinner.tsx
│       └── pages/
│           ├── Dashboard.tsx       # Main chart + chain + trade panel
│           ├── Positions.tsx       # Full positions page
│           ├── Orders.tsx          # Orders history
│           ├── History.tsx         # Trade history + export
│           ├── Analytics.tsx       # Charts + stats
│           └── Settings.tsx        # Account reset + config
│
└── scripts/
    ├── start.sh                    # Start both backend + frontend
    └── seed.py                     # Seed initial account data
```

---

## 11. Open Questions & Decisions

### Q1: Should the Dhan WebSocket provide per-option LTPs?
**Decision: YES.** Subscribe to the option chain instruments that are currently visible in the chain (top 17 strikes × 2 = 34 instruments). Update subscription when expiry changes. This gives truly live position P&L without polling.

### Q2: What lot size to use?
**Decision: 25.** Nifty Bank lot size is 15, Nifty 50 is 25. Use 25 throughout. Display "1 lot = 25 qty" in the UI.

### Q3: How to handle market-closed hours for agent?
**Decision:** Reject with `MARKET_CLOSED` error. Optionally add `force: true` param for testing outside market hours (but flag the trade as "paper" in DB).

### Q4: Should we support sell/short options?
**Decision: NO for Phase 1-4.** Buy-only (CE buy or PE buy). Ansh's stated preference is buy-only options. Add short selling in Phase 5+ if needed.

### Q5: How does the signal engine know which expiry to trade?
**Decision:** Use nearest weekly expiry. Backend `/api/market/expiries` returns sorted list, signal engine picks `expiries[0]` (nearest). Frontend does same.

### Q6: State management in frontend?
**Decision: Zustand.** Lightweight, no boilerplate. Global store holds: `niftyLtp`, `selectedAccount`, `openPositions`, `latestSignal`, `wsStatus`. Avoids prop drilling.

### Q7: How to persist daily_stats?
**Decision:** Run a daily cron at 3:31 PM IST that calculates and inserts daily_stats. Backend has a `/api/admin/close-day` endpoint that can be called manually too.

### Q8: Authentication for human UI?
**Decision: None.** It's localhost-only. No login screen needed.

### Q9: Mobile support?
**Decision: No.** Desktop only (min width 1280px). This is a trading terminal - mobile doesn't make sense for this use case.

### Q10: Should we store Dhan candle data locally?
**Decision:** Cache in memory for the current session (per timeframe). No DB storage. On page reload, re-fetch from Dhan. Historical data beyond what Dhan provides is out of scope.

---

## Implementation Notes for Codex

1. **Start with Phase 1** (static UI). Run `npm create vite@latest frontend -- --template react-ts` in the niftydesk directory.

2. **Dhan credentials** are already configured in `/Users/proxy/trading/nifty_signals/.env`. Copy them to backend `.env`.

3. **Dhan Python SDK** is already installed for signal engine. Reuse `dhanhq` package. Check `/Users/proxy/trading/nifty_signals/requirements.txt` for exact version.

4. **lightweight-charts**: `npm install lightweight-charts`. Import: `import { createChart } from 'lightweight-charts'`. Use v4 API (breaking changes from v3).

5. **Tailwind**: Use `@apply` sparingly. Prefer inline `className` for Kite-style dense tables.

6. **The options chain click-to-fill** is the key UX interaction. Make sure clicking any LTP cell immediately reflects in the trade panel without page reload.

7. **For the signal box**: Signal engine currently writes to a file. The simplest Phase 4 integration is: backend watches the signal output file, imports new signals into the DB, exposes via `/api/signals/latest`. No changes to signal engine needed initially.

8. **Run command**:
   - Backend: `cd backend && uvicorn main:app --reload --port 8000`
   - Frontend: `cd frontend && npm run dev` (proxy API calls to port 8000 in vite.config.ts)

---

*End of Lite Plan v1.0*
*Ready for Codex implementation.*
