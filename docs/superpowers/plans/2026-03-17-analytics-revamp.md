# Analytics Page Revamp — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the analytics page into a clean, insightful trading journal that answers "what am I good at, what am I bad at, and how is my capital trending" — using the platform's existing Kite Dark design language.

**Architecture:** Two-layer approach: (1) **Storage layer** captures rich market context at fill time — spot, VIX, days to expiry — so we never lose data. (2) **Display layer** buckets and slices this raw data at render time, so we can change bucketing logic without touching stored data. Backend sends enriched trades with raw context fields. Frontend does all bucketing/aggregation.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React 19 + Tailwind CSS 4 + Zustand (frontend). No lightweight-charts on analytics page. Custom SVG/CSS charts only.

---

## Core Principle: Store Raw, Bucket at Display Time

**What we store per fill (at execution time):**
- `spot_at_fill` — Nifty spot price
- `vix_at_fill` — India VIX value

**What we compute per closed trade (from fills, at query time):**
- `entry_price`, `exit_price` — premium paid/received
- `entry_date`, `exit_date` — calendar dates (not just datetimes)
- `hold_days` — calendar days held (0 = intraday, 1+ = multi-day)
- `expiry_date` — parsed from symbol
- `days_to_expiry_at_entry` — expiry_date minus entry_date
- `days_to_expiry_at_exit` — expiry_date minus exit_date
- `spot_at_entry`, `spot_at_exit` — from fills
- `vix_at_entry`, `vix_at_exit` — from fills
- `atm_distance` — strike minus spot (signed, in points)
- `lots` — quantity / lot_size

**What we derive per trade for behavioral/context analysis (frontend-side):**
- `premium_captured_pct` — `(entry_price - exit_price) / entry_price * 100` for shorts, inverse for longs
- `spot_move_during_trade` — `spot_at_exit - spot_at_entry` (how much Nifty moved)
- `vix_change_during_trade` — `vix_at_exit - vix_at_entry` (vol expansion/compression)
- `entry_hour` — hour of day from `entry_time` (for time-of-day bucketing)
- `entry_day_of_week` — day name from `entry_time`
- `is_expiry_week` — `days_to_expiry_at_entry <= 4` (weekly expiry context)
- `is_overnight` — `hold_days >= 1` (carried overnight)
- Revenge trading detection: compare each trade's `entry_time` against the previous trade's `exit_time` — if a loss was followed by entry within 30 minutes

**The frontend decides how to bucket all of this.** If we want "by hold duration" in days, or hours, or weeks — that's a display choice, not a storage choice. Same for moneyness thresholds, expiry distance grouping, etc.

---

## Design Principles

### Visual language (from studying the platform)
- **Page header**: `h-9`, `border-b border-border-primary`, `px-3`, `text-[12px] font-medium`
- **Section panels**: `rounded bg-bg-secondary p-3` or `p-4`
- **Section titles**: `text-[11px] font-medium text-text-secondary` or `text-xs font-medium text-text-secondary`
- **Data tables**: `text-xs`, headers `font-normal text-text-muted uppercase tracking-wider`, rows `border-b border-border-secondary/40 hover:bg-bg-hover`
- **Numbers**: always `tabular-nums`, currency with `₹` and `toLocaleString('en-IN')`
- **P&L coloring**: profit → `text-profit` (#4caf50), loss → `text-loss` (#e53935)
- **Tags**: `text-[9px] px-1.5 py-px rounded font-medium`, CE → `bg-signal/10 text-signal`, PE → `bg-[#ab47bc]/10 text-[#ba68c8]`
- **Backgrounds**: primary `#1a1a1a`, secondary `#252525`, tertiary `#2a2a2a`
- **No third-party chart widgets** — TradingView watermark looks terrible. Custom SVG/HTML only.
- **Empty states**: centered icon + text, muted

### What the page must answer
1. **How is my capital trending?** → Equity curve (custom SVG), P&L heatmap
2. **Do I have an edge?** → Win rate, expectancy, risk:reward, profit factor
3. **What types of trades work for me?** → CE vs PE, Long vs Short (win rates + P&L)
4. **What trade characteristics are profitable?** → By hold duration, moneyness, days-to-expiry, size, VIX regime, time of day, day of week, expiry week vs non-expiry
5. **Am I managing risk well?** → Max drawdown, biggest win/loss, streaks, Sharpe
6. **Am I disciplined?** → Avg hold time winners vs losers, revenge trading detection, overtrading signal
7. **How does market context affect me?** → VIX change during trade, spot move during trade, gap risk for overnights, premium capture %
8. **What are my actual trades?** → Trade log table

---

## Chunk 1: Backend — Rich Context Storage

### Task 1: Add market context columns to Fill model

Store spot price and VIX at every fill execution. This is the foundation — once stored, we can derive any insight later.

**Files:**
- Modify: `backend/models.py` — add columns to Fill
- Create: `backend/alembic/versions/xxxx_add_market_context_to_fills.py` — migration
- Modify: `backend/services/trading_service.py` — populate at fill creation

- [ ] **Step 1: Add columns to Fill model**

In `backend/models.py`, add to the `Fill` class:
```python
spot_at_fill = Column(Numeric(14, 2), nullable=True)
vix_at_fill = Column(Numeric(8, 2), nullable=True)
```

Both nullable because: (a) historical fills won't have this data, (b) market data might be unavailable at fill time.

- [ ] **Step 2: Generate and run alembic migration**

```bash
cd backend && python -m alembic revision --autogenerate -m "add market context to fills"
cd backend && python -m alembic upgrade head
```

- [ ] **Step 3: Populate context at fill creation**

In `backend/services/trading_service.py`, where `Fill` records are created, capture current market state:

```python
from services.market_data import get_cached_snapshot

def _capture_market_context() -> tuple[float | None, float | None]:
    """Capture spot and VIX at this moment. Returns (spot, vix)."""
    try:
        snapshot = get_cached_snapshot()
        if snapshot:
            return snapshot.get("spot"), snapshot.get("vix")
    except Exception:
        pass
    return None, None
```

Call this when creating fills and pass `spot_at_fill=spot`, `vix_at_fill=vix`.

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/alembic/versions/ backend/services/trading_service.py
git commit -m "feat(analytics): capture spot and VIX at fill execution"
```

### Task 2: Enrich DetailedTradeSummary with raw context

Extend the trade summary to carry all raw context needed for any future bucketing. No bucketing in the backend — just raw values.

**Files:**
- Modify: `backend/schemas.py` — extend `DetailedTradeSummary`
- Modify: `backend/services/analytics_service.py` — compute new fields in `_build_closed_trades`

- [ ] **Step 1: Extend DetailedTradeSummary schema**

```python
class DetailedTradeSummary(BaseModel):
    symbol: str
    strike: int
    option_type: Literal["CE", "PE"]
    direction: Literal["LONG", "SHORT"]
    quantity: int
    lots: int                                    # quantity / lot_size
    entry_time: datetime
    exit_time: datetime
    hold_seconds: float
    hold_days: int                               # calendar days: (exit_date - entry_date).days
    realized_pnl: float
    entry_price: float                           # avg premium at entry
    exit_price: float                            # avg premium at exit
    expiry_date: str                             # YYYY-MM-DD from symbol
    days_to_expiry_at_entry: int                 # expiry_date - entry_date
    days_to_expiry_at_exit: int                  # expiry_date - exit_date
    spot_at_entry: float | None = None           # Nifty spot when opened
    spot_at_exit: float | None = None            # Nifty spot when closed
    vix_at_entry: float | None = None            # VIX when opened
    vix_at_exit: float | None = None             # VIX when closed
    atm_distance: int | None = None              # strike - spot_at_entry (signed, points)
```

- [ ] **Step 2: Update `_build_closed_trades` to populate new fields**

When matching entry/exit fills in `_build_closed_trades`:
- Parse `expiry_date` from symbol: `symbol.split("_")[1]`
- `hold_days = (exit_fill.executed_at.date() - entry_fill.executed_at.date()).days`
- `days_to_expiry_at_entry = (expiry_date - entry_fill.executed_at.date()).days`
- `days_to_expiry_at_exit = (expiry_date - exit_fill.executed_at.date()).days`
- `entry_price = float(entry_fill.price)`, `exit_price = float(exit_fill.price)`
- `spot_at_entry = float(entry_fill.spot_at_fill)` if available
- `spot_at_exit = float(exit_fill.spot_at_fill)` if available
- `vix_at_entry = float(entry_fill.vix_at_fill)` if available
- `vix_at_exit = float(exit_fill.vix_at_fill)` if available
- `atm_distance = strike - spot_at_entry` if spot available
- `lots = quantity // lot_size` (use `config.NIFTY_LOT_SIZE`)

- [ ] **Step 3: Commit**

```bash
git add backend/schemas.py backend/services/analytics_service.py
git commit -m "feat(analytics): enrich trade summaries with raw market context"
```

### Task 3: New enriched analytics endpoint

Single endpoint that returns everything the frontend needs. Aggregate metrics are computed server-side (they need all trades). Bucketing/slicing is NOT done server-side — raw trades go to the frontend.

**Files:**
- Modify: `backend/schemas.py` — add `EnrichedAnalyticsResponse`
- Modify: `backend/services/analytics_service.py` — add `enriched_analytics_summary`
- Modify: `backend/routers/analytics.py` — add `/enriched` endpoint

- [ ] **Step 1: Add EnrichedAnalyticsResponse schema**

```python
class EnrichedAnalyticsResponse(BaseModel):
    portfolio_id: str
    # Headline
    total_closed_trades: int
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float
    # Edge
    win_rate: float
    expectancy: float
    risk_reward: float
    profit_factor: float
    # Risk
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    biggest_win: float
    biggest_loss: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_hold_seconds: float
    avg_win_hold_seconds: float
    avg_loss_hold_seconds: float
    # Curves
    equity_curve: list[AnalyticsPoint]
    pnl_by_day: list[AnalyticsPoint]
    drawdown_curve: list[AnalyticsPoint]
    # Raw trades — frontend does all bucketing
    closed_trades: list[DetailedTradeSummary]
```

Key: **no `by_*` slice fields**. The frontend receives `closed_trades` with all context fields and groups them however it wants. This means we can add new bucketing dimensions (by VIX regime, by day of week, by time of day) without any backend changes.

- [ ] **Step 2: Implement `enriched_analytics_summary`**

Reuses existing helpers:
- `_build_closed_trades` (enriched) for trade list
- `_risk_ratios` for Sharpe/Sortino/Calmar/drawdown
- `analytics_summary` for equity_curve/pnl_by_day
- `funds_summary` for unrealized/equity

Computes edge metrics:
```python
wins = [t for t in trades if t.realized_pnl > 0]
losses = [t for t in trades if t.realized_pnl < 0]
avg_win = mean(t.realized_pnl for t in wins) if wins else 0
avg_loss = abs(mean(t.realized_pnl for t in losses)) if losses else 0
win_rate = len(wins) / len(trades) * 100 if trades else 0
expectancy = (win_rate/100 * avg_win) - ((1 - win_rate/100) * avg_loss)
risk_reward = avg_win / avg_loss if avg_loss > 0 else 0
profit_factor = sum(w.realized_pnl for w in wins) / abs(sum(l.realized_pnl for l in losses)) if losses else 0
```

Behavioral metrics:
```python
avg_win_hold = mean(t.hold_seconds for t in wins) if wins else 0
avg_loss_hold = mean(t.hold_seconds for t in losses) if losses else 0
```

- [ ] **Step 3: Add `/enriched` endpoint**

```python
@router.get("/enriched", response_model=EnrichedAnalyticsResponse)
def enriched_analytics(
    portfolio_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    user_portfolio_ids: list[str] = Depends(get_user_portfolio_ids),
):
    if portfolio_id not in user_portfolio_ids:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return enriched_analytics_summary(db, portfolio_id)
```

Place BEFORE the `/{portfolio_id}` legacy route.

- [ ] **Step 4: Commit**

```bash
git add backend/schemas.py backend/services/analytics_service.py backend/routers/analytics.py
git commit -m "feat(analytics): enriched endpoint with edge metrics and raw context trades"
```

---

## Chunk 2: Frontend — Custom Chart Components

No third-party charting libraries. Small SVG/CSS components matching Kite Dark.

### Task 4: SVG equity curve

**Files:**
- Create: `frontend/src/components/analytics/EquityCurveSVG.tsx`

- [ ] **Step 1: Build component**

Props: `data: Array<{ label: string; value: number }>`, `height?: number` (default 180)

Implementation:
- Pure SVG, `width="100%"` with `preserveAspectRatio="none"` and a `viewBox`
- Normalize data points to viewBox coordinates
- `<path>` for line — stroke `#387ed1`, stroke-width 1.5, no fill
- `<path>` for area below line — `fill="url(#equity-gradient)"`
- `<linearGradient>` vertical: `rgba(56,126,209,0.12)` → `transparent`
- Dashed horizontal line at starting value (baseline) — stroke `#333`, dash `4,4`
- No axes, no labels, no crosshairs — the headline numbers provide context
- Responsive: wrap in a div, SVG fills container width
- Empty state: `text-text-muted text-xs` centered placeholder

- [ ] **Step 2: Commit**

### Task 5: Horizontal bar chart component

Reusable for daily P&L and any other bar visualization.

**Files:**
- Create: `frontend/src/components/analytics/HBarChart.tsx`

- [ ] **Step 1: Build component**

Props: `rows: Array<{ label: string; value: number; sub?: string }>`, `maxRows?: number`

Pure Tailwind (not SVG). Each row:
```
[label 70px] [bar flex-1 h-[14px]] [value 76px right-aligned]
```
- Bar: `rounded-[2px]`, `bg-profit/20` or `bg-loss/20`, width proportional to `|value| / max(|values|)`
- Value: `text-[10px] font-medium tabular-nums`, colored by sign
- Label: `text-[10px] text-text-muted tabular-nums`
- Spacing: `py-[3px]`, `space-y-px`

- [ ] **Step 2: Commit**

### Task 6: Trade slice panel

Reusable component for showing a bucketed breakdown of trades.

**Files:**
- Create: `frontend/src/components/analytics/SlicePanel.tsx`

- [ ] **Step 1: Build component**

Props:
```typescript
type SliceRow = {
  label: string
  count: number
  wins: number
  winRate: number
  totalPnl: number
  avgPnl: number
}
type SlicePanelProps = {
  title: string
  rows: SliceRow[]
}
```

Renders a `rounded bg-bg-secondary p-3` panel:
- Title: `text-[11px] font-medium text-text-secondary mb-2`
- Each row: flex with items between
  - Left: label + count (`text-[11px]`)
  - Right: win rate (`text-[10px] text-text-muted`) + P&L value (colored, `text-[11px] font-medium tabular-nums`)
- Rows separated by `border-b border-border-secondary/40`
- Matches Positions/History table row pattern

- [ ] **Step 2: Build `sliceTrades` utility**

In `frontend/src/components/analytics/slicing.ts`:

```typescript
export type SliceRow = { label: string; count: number; wins: number; winRate: number; totalPnl: number; avgPnl: number }

export function sliceTrades<T>(
  trades: T[],
  labelFn: (t: T) => string,
): SliceRow[] {
  const buckets = new Map<string, T[]>()
  for (const t of trades) {
    const key = labelFn(t)
    const arr = buckets.get(key) ?? []
    arr.push(t)
    buckets.set(key, arr)
  }
  // ... aggregate each bucket into SliceRow
}
```

This single function handles ALL bucketing:
```typescript
// ── Basic attribution ──
sliceTrades(trades, t => t.option_type)                                   // CE vs PE
sliceTrades(trades, t => t.direction)                                      // LONG vs SHORT

// ── Trade characteristics ──
sliceTrades(trades, t => {                                                 // Hold duration
  if (t.hold_days === 0) return 'Intraday'
  if (t.hold_days <= 2) return '1-2 days'
  if (t.hold_days <= 7) return '3-7 days'
  return '7+ days'
})
sliceTrades(trades, t => {                                                 // Moneyness
  if (t.atm_distance == null) return 'Unknown'
  const d = Math.abs(t.atm_distance)
  if (d <= 50) return 'ATM'
  const isOtm = (t.option_type === 'CE' && t.atm_distance > 0)
             || (t.option_type === 'PE' && t.atm_distance < 0)
  return isOtm ? 'OTM' : 'ITM'
})
sliceTrades(trades, t => {                                                 // Days to expiry
  if (t.days_to_expiry_at_entry === 0) return 'Expiry day'
  if (t.days_to_expiry_at_entry <= 2) return '1-2 days out'
  if (t.days_to_expiry_at_entry <= 5) return '3-5 days out'
  return '5+ days out'
})
sliceTrades(trades, t => `${t.lots} lot${t.lots > 1 ? 's' : ''}`)        // By size

// ── Market context ──
sliceTrades(trades, t => {                                                 // VIX regime at entry
  if (t.vix_at_entry == null) return 'Unknown'
  if (t.vix_at_entry < 13) return 'Low VIX (<13)'
  if (t.vix_at_entry < 18) return 'Normal VIX (13-18)'
  return 'High VIX (>18)'
})
sliceTrades(trades, t => {                                                 // VIX change during trade
  if (t.vix_at_entry == null || t.vix_at_exit == null) return 'Unknown'
  const delta = t.vix_at_exit - t.vix_at_entry
  if (delta < -1) return 'VIX fell (>1pt)'
  if (delta > 1) return 'VIX rose (>1pt)'
  return 'VIX flat'
})
sliceTrades(trades, t => {                                                 // Spot move during trade
  if (t.spot_at_entry == null || t.spot_at_exit == null) return 'Unknown'
  const move = Math.abs(t.spot_at_exit - t.spot_at_entry)
  if (move < 50) return 'Nifty <50pts'
  if (move < 100) return 'Nifty 50-100pts'
  if (move < 200) return 'Nifty 100-200pts'
  return 'Nifty 200+pts'
})

// ── Time patterns ──
sliceTrades(trades, t =>                                                   // Day of week
  ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][new Date(t.entry_time).getDay()]
)
sliceTrades(trades, t => {                                                 // Time of day
  const h = new Date(t.entry_time).getHours()
  const m = new Date(t.entry_time).getMinutes()
  const mins = h * 60 + m
  if (mins < 600) return 'Pre-open (<10:00)'
  if (mins < 690) return 'Morning (10:00-11:30)'
  if (mins < 810) return 'Midday (11:30-13:30)'
  return 'Afternoon (13:30+)'
})
sliceTrades(trades, t =>                                                   // Expiry week vs not
  t.days_to_expiry_at_entry <= 4 ? 'Expiry week' : 'Non-expiry week'
)

// ── Overnight/Gap ──
sliceTrades(trades, t =>                                                   // Overnight exposure
  t.hold_days >= 1 ? 'Overnight/multi-day' : 'Intraday (closed same day)'
)
```

The beauty: adding a new dimension is a one-liner. No backend changes ever.

- [ ] **Step 3: Build behavioral analytics utilities**

In `frontend/src/components/analytics/behavioral.ts`:

```typescript
import type { DetailedTradeSummary } from '../../lib/api'

export type BehavioralInsight = {
  label: string
  description: string
  value: string
  verdict: 'good' | 'bad' | 'neutral'
}

/**
 * Revenge trading: entry within 30min of a losing trade's exit.
 * Returns stats on revenge trades vs normal trades.
 */
export function detectRevengeTrades(trades: DetailedTradeSummary[]): BehavioralInsight | null {
  const sorted = [...trades].sort((a, b) =>
    new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime()
  )
  let revengeCount = 0
  let revengeWins = 0
  let revengePnl = 0

  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1]
    const curr = sorted[i]
    if (prev.realized_pnl >= 0) continue // previous wasn't a loss
    const gap = (new Date(curr.entry_time).getTime() - new Date(prev.exit_time).getTime()) / 60000
    if (gap <= 30 && gap >= 0) {
      revengeCount++
      if (curr.realized_pnl > 0) revengeWins++
      revengePnl += curr.realized_pnl
    }
  }

  if (revengeCount === 0) return null
  const wr = Math.round((revengeWins / revengeCount) * 100)
  return {
    label: 'Revenge Trading',
    description: `${revengeCount} trades entered within 30min of a loss`,
    value: `${wr}% win rate, ${revengePnl >= 0 ? '+' : ''}₹${Math.abs(revengePnl).toFixed(0)} P&L`,
    verdict: wr < 40 ? 'bad' : 'neutral',
  }
}

/**
 * Overtrading: days with 3+ trades vs 1-2 trades.
 * Compares avg daily P&L.
 */
export function detectOvertrading(trades: DetailedTradeSummary[]): BehavioralInsight | null {
  const byDay = new Map<string, DetailedTradeSummary[]>()
  for (const t of trades) {
    const day = new Date(t.entry_time).toISOString().slice(0, 10)
    byDay.set(day, [...(byDay.get(day) ?? []), t])
  }

  let heavyDays = 0, heavyPnl = 0
  let lightDays = 0, lightPnl = 0
  for (const [, dayTrades] of byDay) {
    const pnl = dayTrades.reduce((s, t) => s + t.realized_pnl, 0)
    if (dayTrades.length >= 3) { heavyDays++; heavyPnl += pnl }
    else { lightDays++; lightPnl += pnl }
  }

  if (heavyDays === 0 || lightDays === 0) return null
  const heavyAvg = heavyPnl / heavyDays
  const lightAvg = lightPnl / lightDays
  return {
    label: 'Overtrading',
    description: `${heavyDays} days with 3+ trades vs ${lightDays} days with 1-2`,
    value: `Heavy: ₹${heavyAvg.toFixed(0)}/day, Light: ₹${lightAvg.toFixed(0)}/day`,
    verdict: heavyAvg < lightAvg ? 'bad' : 'neutral',
  }
}

/**
 * Conviction sizing: do larger trades (2+ lots) win more?
 */
export function analyzeConvictionSizing(trades: DetailedTradeSummary[]): BehavioralInsight | null {
  const big = trades.filter(t => t.lots >= 2)
  const small = trades.filter(t => t.lots === 1)
  if (big.length < 2 || small.length < 2) return null

  const bigWR = Math.round(big.filter(t => t.realized_pnl > 0).length / big.length * 100)
  const smallWR = Math.round(small.filter(t => t.realized_pnl > 0).length / small.length * 100)
  return {
    label: 'Conviction Sizing',
    description: `${big.length} trades at 2+ lots vs ${small.length} at 1 lot`,
    value: `Big: ${bigWR}% win rate, Small: ${smallWR}% win rate`,
    verdict: bigWR > smallWR ? 'good' : bigWR < smallWR - 10 ? 'bad' : 'neutral',
  }
}

/**
 * Premium capture: what % of entry premium was captured.
 */
export function analyzePremiumCapture(trades: DetailedTradeSummary[]): BehavioralInsight | null {
  const withPrices = trades.filter(t => t.entry_price > 0 && t.exit_price >= 0)
  if (withPrices.length === 0) return null

  const captures = withPrices.map(t => {
    if (t.direction === 'SHORT') return ((t.entry_price - t.exit_price) / t.entry_price) * 100
    return ((t.exit_price - t.entry_price) / t.entry_price) * 100
  })
  const avg = captures.reduce((s, v) => s + v, 0) / captures.length
  return {
    label: 'Premium Capture',
    description: `Avg % of entry premium captured per trade`,
    value: `${avg >= 0 ? '+' : ''}${avg.toFixed(1)}%`,
    verdict: avg > 0 ? 'good' : 'bad',
  }
}

/**
 * Gap risk: for overnight holds, was the opening gap helpful or harmful?
 * Approximated by comparing spot_at_exit to spot_at_entry for multi-day trades.
 */
export function analyzeGapRisk(trades: DetailedTradeSummary[]): BehavioralInsight | null {
  const overnight = trades.filter(t => t.hold_days >= 1 && t.spot_at_entry != null && t.spot_at_exit != null)
  if (overnight.length < 2) return null

  const gapHelped = overnight.filter(t => {
    const spotMove = t.spot_at_exit! - t.spot_at_entry!
    // For long calls / short puts, spot up = good. For short calls / long puts, spot down = good.
    const wantsUp = (t.option_type === 'CE' && t.direction === 'LONG') || (t.option_type === 'PE' && t.direction === 'SHORT')
    return wantsUp ? spotMove > 0 : spotMove < 0
  }).length

  const pct = Math.round((gapHelped / overnight.length) * 100)
  const overnightPnl = overnight.reduce((s, t) => s + t.realized_pnl, 0)
  return {
    label: 'Overnight Gap Exposure',
    description: `${overnight.length} trades held overnight`,
    value: `Gap helped ${pct}% of the time, total P&L: ₹${overnightPnl.toFixed(0)}`,
    verdict: pct > 55 ? 'good' : pct < 45 ? 'bad' : 'neutral',
  }
}
```

- [ ] **Step 3: Commit**

---

## Chunk 3: Frontend — Analytics Page Assembly

### Task 7: Rewrite Analytics.tsx

**Files:**
- Rewrite: `frontend/src/pages/Analytics.tsx`
- Modify: `frontend/src/lib/api.ts` — add types and fetch function

- [ ] **Step 1: Add API types and fetch**

In `frontend/src/lib/api.ts`:
```typescript
export type EnrichedAnalyticsResponse = components['schemas']['EnrichedAnalyticsResponse']

export async function fetchEnrichedAnalytics(portfolioId: string) {
  return rawFetch<EnrichedAnalyticsResponse>(
    `/api/v1/analytics/enriched?portfolio_id=${encodeURIComponent(portfolioId)}`
  )
}
```

After backend is updated, regenerate schema types:
```bash
cd frontend && npx openapi-typescript http://localhost:8000/api/v1/openapi.json -o src/lib/api-schema.d.ts
```

If schema gen isn't immediately available, define types manually.

- [ ] **Step 2: Page layout — top to bottom**

```
┌─────────────────────────────────────────────────────┐
│ Analytics                              (page header) │
├─────────────────────────────────────────────────────┤
│ TOTAL P&L  +₹18,450   EQUITY ₹5,18,450             │
│ UNREALISED +₹0   WIN RATE 62.5% (15W / 9L)         │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐ │
│ │ Equity Curve (EquityCurveSVG, full width)       │ │
│ └─────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐ │
│ │ P&L Heatmap (existing component, full width)    │ │
│ └─────────────────────────────────────────────────┘ │
├────────────────────────┬────────────────────────────┤
│ Your Edge              │ Risk Profile               │
│ Expectancy   ₹768      │ Max Drawdown   ₹3,200      │
│ Risk:Reward  1:1.58    │ Biggest Win    ₹4,200      │
│ Profit Factor 1.58     │ Biggest Loss   ₹2,100      │
│                        │ Sharpe         1.24         │
│ Behavior               │ Win Streak     6            │
│ Avg win hold   2d      │ Loss Streak    3            │
│ Avg loss hold  4h      │                             │
│ Verdict: Letting       │                             │
│   winners run          │                             │
├────────────────────────┴────────────────────────────┤
│ Trade Insights                                       │
├────────┬────────┬──────────┬────────────────────────┤
│By Type │By Dir  │By Money  │ By Hold Duration        │
│CE  +12k│LONG+11k│OTM +8k  │ Intraday   -1.2k       │
│PE  +6k │SHT +7k│ATM +7k  │ 1-2 days   +5k         │
│        │        │ITM +3k  │ 3-7 days   +10k        │
│        │        │         │ 7+ days    +4k         │
├────────┼────────┼─────────┼────────────────────────┤
│By DTE  │By Size │By VIX   │ By VIX Change           │
│Exp day │1 lot   │Low <13  │ VIX fell     +8k        │
│1-2 days│2 lots  │Normal   │ VIX rose     -2k        │
│3-5 days│3+ lots │High >18 │ VIX flat     +4k        │
├────────┼────────┼─────────┼────────────────────────┤
│By Day  │By Time │By Spot  │ By Expiry Week          │
│Mon +2k │Morning │<50pts   │ Expiry wk    +10k       │
│Tue +4k │Midday  │50-100pts│ Non-expiry   +8k        │
│...     │Afternoon│100-200 │                          │
│        │        │200+pts  │                          │
├────────┴────────┴─────────┴────────────────────────┤
│ Behavioral Insights                                  │
│ ┌──────────────┬──────────────┬───────────────────┐ │
│ │ Revenge      │ Overtrading  │ Conviction Sizing │ │
│ │ Trading      │              │                   │ │
│ │ 3 trades     │ Heavy days:  │ Big (2+ lots):    │ │
│ │ after losses │ ₹-800/day    │ 70% win rate      │ │
│ │ 25% win rate │ Light days:  │ Small (1 lot):    │ │
│ │              │ ₹+1200/day   │ 55% win rate      │ │
│ ├──────────────┼──────────────┼───────────────────┤ │
│ │ Premium      │ Overnight    │                   │ │
│ │ Capture      │ Gap Risk     │                   │ │
│ │ Avg +22.4%   │ Gap helped   │                   │ │
│ │ of premium   │ 60% of time  │                   │ │
│ └──────────────┴──────────────┴───────────────────┘ │
├─────────────────────────────────────────────────────┤
│ Recent Days (HBarChart, last 15)                     │
├─────────────────────────────────────────────────────┤
│ Trade Log (table)                                    │
│ Strike│CE/PE│Dir│Lots│Hold│DTE│Spot│VIX│P&L          │
└─────────────────────────────────────────────────────┘
```

- [ ] **Step 3: Headline section**

`flex items-baseline gap-6 mb-1` at the top. Four inline stats:
- Total P&L (xl size, colored)
- Equity (sm size)
- Unrealised (sm size, colored)
- Win Rate with W/L count

- [ ] **Step 4: Equity curve section**

Full-width `rounded bg-bg-secondary p-3`. Contains `<EquityCurveSVG>`.

- [ ] **Step 5: P&L Heatmap section**

Full-width. Existing `<PnLHeatmap>` component. Unchanged. The hero visual.

- [ ] **Step 6: Your Edge + Risk Profile**

Grid `grid-cols-5 gap-3`. Edge = `col-span-3`, Risk = `col-span-2`.

**Edge panel** (`rounded bg-bg-secondary p-3`):
- Key-value rows for Expectancy, Risk:Reward, Profit Factor
- Separator then Behavior subsection:
  - Avg win hold vs avg loss hold (now in days/hours as appropriate)
  - Computed verdict: "Letting winners run" vs "Cutting winners short"

**Risk panel** (`rounded bg-bg-secondary p-3`):
- Simple key-value list matching the platform's clean style

- [ ] **Step 7: Trade Insights section**

Section title "Trade Insights", then three rows of `<SlicePanel>` components:

Row 1 (4 columns): By Type, By Direction, By Moneyness, By Hold Duration
Row 2 (4 columns): By Days to Expiry, By Size, By VIX Regime, By VIX Change
Row 3 (4 columns): By Day of Week, By Time of Day, By Spot Move, By Expiry Week

Each panel calls `sliceTrades(trades, labelFn)` with the appropriate bucketing function from `slicing.ts`. Panels with zero data (e.g. VIX unknown for all trades) are hidden.

- [ ] **Step 8: Behavioral Insights section**

Section title "Behavioral Insights". A grid of insight cards rendered from the behavioral analytics utilities.

Call all detector functions:
```typescript
const insights = [
  detectRevengeTrades(trades),
  detectOvertrading(trades),
  analyzeConvictionSizing(trades),
  analyzePremiumCapture(trades),
  analyzeGapRisk(trades),
].filter(Boolean)
```

Each insight card (`rounded bg-bg-secondary p-3`):
- Label as title (`text-[11px] font-medium`)
- Description in muted text
- Value highlighted with verdict coloring:
  - `good` → green left border accent
  - `bad` → red left border accent
  - `neutral` → no accent

Cards in a `grid grid-cols-3 gap-3` (or 2 cols if fewer insights). Hidden entirely if no insights detected (not enough trade data).

- [ ] **Step 9: Recent Days (was Step 8)**

Full-width panel with `<HBarChart>`, last 15 days from `pnl_by_day` reversed.

- [ ] **Step 10: Trade Log table**

Full-width panel. Table columns: Strike, CE/PE (tag), Direction, Lots, Hold (days/hours), DTE at entry, Spot at entry, VIX at entry, P&L. Most recent first. Same table patterns as History/Positions.

- [ ] **Step 11: Data loading**

```typescript
useEffect(() => {
  if (!selectedPortfolioId) return
  let active = true
  setLoading(true)
  fetchEnrichedAnalytics(selectedPortfolioId)
    .then(d => { if (active) setData(d) })
    .catch(() => {}) // fall back to basic analytics from store
    .finally(() => { if (active) setLoading(false) })
  return () => { active = false }
}, [selectedPortfolioId])
```

Falls back to `analytics` from the Zustand store for headline/equity curve/heatmap while enriched data loads. Enriched data is fetched on page visit only (not polled — it's heavy).

- [ ] **Step 12: Commit**

```bash
git add frontend/src/pages/Analytics.tsx frontend/src/components/analytics/ frontend/src/lib/api.ts
git commit -m "feat(analytics): complete page revamp with trade insights, behavioral analysis, and custom charts"
```

---

## Chunk 4: Cleanup

### Task 8: Remove lightweight-charts from Analytics

Verify Analytics.tsx has no `lightweight-charts` imports. The library stays in `package.json` — it's still used by `NiftyChart.tsx` on the Dashboard.

- [ ] **Step 1: Verify**
- [ ] **Step 2: Commit if needed**

### Task 9: Restore vite proxy

**Files:**
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Change proxy back to production**

```typescript
proxy: {
  '/api/v1/ws': {
    target: 'wss://lite-options-api-production.up.railway.app',
    ws: true,
  },
  '/api': {
    target: 'https://lite-options-api-production.up.railway.app',
    changeOrigin: true,
  },
},
```

- [ ] **Step 2: Commit**

### Task 10: Smoke test all pages

- [ ] Navigate to every route and verify no regressions: Dashboard, Positions, Orders, History, Funds, Analytics, Settings.

---

## Chunk 5: Funds Page Tweaks

To be defined with user in follow-up conversation.

---

## What's Now Included (was "Future")

All of these are now part of the plan — implemented in Chunk 2 (slicing) and Chunk 3 (page assembly):

- **By day of week** — are Mondays better than Fridays?
- **By time of day** — morning (pre-10), morning, midday, afternoon entries
- **By VIX regime** — low/normal/high VIX at entry
- **By VIX change** — did VIX rise or fall during the trade?
- **By spot move** — how much did Nifty move during the trade?
- **By expiry week** — expiry week vs non-expiry week
- **Revenge trading** — trades entered within 30min of a loss
- **Overtrading** — heavy vs light trading days
- **Conviction sizing** — do bigger trades win more?
- **Premium capture** — avg % of premium captured per trade
- **Overnight gap risk** — did gaps help or hurt overnight holds?

## True Future Dimensions (not yet planned)

These would need additional data or more complex analysis:

- **By month** — seasonal patterns (need enough data across months)
- **By premium level** — cheap vs expensive options (bucket by entry_price)
- **Intraday P&L curve** — how P&L evolves during the day (needs tick-level tracking)
- **Max adverse excursion** — worst drawdown within each trade (needs intraday price snapshots during open positions)
- **Correlation with market regime** — trending vs ranging market (needs rolling ATR or similar)
