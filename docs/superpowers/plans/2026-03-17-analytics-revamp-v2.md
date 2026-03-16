# Analytics & Funds Revamp — Complete Plan v2

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the analytics page into a beautiful, insightful trading journal that matches the quality of the platform's best elements (Dashboard options chain, FII/DII modal, keyboard shortcuts modal). Also redesign the Funds page to match.

**Architecture:** Backend stores raw market context per fill (spot, VIX). Enriched endpoint returns aggregate metrics + raw trades. Frontend does all bucketing/slicing at display time. No third-party chart widgets.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React 19 + Tailwind CSS 4 + Zustand (frontend). Custom SVG/CSS charts only.

---

## Current Status (what's already done)

### Backend ✅
- `spot_at_fill` and `vix_at_fill` columns added to Fill model with migration
- `DetailedTradeSummary` enriched with: `lots`, `hold_days`, `entry_price`, `exit_price`, `expiry_date`, `days_to_expiry_at_entry`, `days_to_expiry_at_exit`, `spot_at_entry/exit`, `vix_at_entry/exit`, `atm_distance`
- `EnrichedAnalyticsResponse` schema with edge metrics (win_rate, expectancy, risk_reward, profit_factor), risk metrics (max_drawdown, biggest_win/loss, streaks, hold times), curves (equity, pnl_by_day, drawdown), raw trades
- `GET /api/v1/analytics/enriched` endpoint live
- All 47 existing tests still pass

### Frontend Components ✅
- `components/analytics/types.ts` — Trade type, SliceRow, BehavioralInsight types
- `components/analytics/EquityCurveSVG.tsx` — Pure SVG area chart, responsive, no TradingView
- `components/analytics/HBarChart.tsx` — Horizontal bar chart for daily P&L
- `components/analytics/SlicePanel.tsx` — Bucketed trade breakdown panel
- `components/analytics/slicing.ts` — `sliceTrades()` + 13 pre-built slicers (option type, direction, moneyness, hold duration, DTE, size, VIX regime, VIX change, spot move, day of week, time of day, expiry week)
- `components/analytics/behavioral.ts` — 5 detectors (revenge trading, overtrading, conviction sizing, premium capture, gap risk)
- `api.ts` has `fetchEnrichedAnalytics` and `EnrichedAnalyticsResponse` type

### What's NOT done (what this plan covers)
1. **Analytics.tsx** — the page itself is ugly, wrong design patterns, doesn't match platform quality
2. **PnLHeatmap.tsx** — cells don't fill container width, doesn't look like GitHub contributions
3. **Funds.tsx** — needs redesign to match Dashboard quality (user explicitly said Funds is ugly too)
4. **vite.config.ts** — proxy still pointing to localhost:8000 instead of production

---

## Design Reference: The Gold Standard

From user screenshots, these are the platform elements that define "beautiful":

### FII/DII Modal Pattern
```
┌─────────────────────────────────────────────────┐
│ FII / DII                      < 2026-03-16 > ✕ │  ← Title + subtitle + controls
│ Participant-wise net positions                   │
├─────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────┐ │
│ │ FII   Adding longs              [Bearish]  │ │  ← Card: name + action + badge
│ │ ┌──────────┬──────────┬───────────────────┐ │ │
│ │ │ FUTURES  │ CALLS    │ PUTS              │ │ │  ← 3-col with divide-x
│ │ │ -248.8K  │ -244.7K  │ +426.1K           │ │ │  ← LARGE colored numbers
│ │ │ +11.8K   │ +15.9K   │ -29.4K            │ │ │  ← smaller change values
│ │ └──────────┴──────────┴───────────────────┘ │ │
│ └─────────────────────────────────────────────┘ │
```

**Key patterns extracted:**
- **Cards**: `rounded border border-border-primary` (NOT just `bg-bg-secondary`, needs the border)
- **Card headers**: `px-4 py-3 border-b border-border-primary` with title left, badge/controls right
- **Title**: `text-[14px] font-semibold text-text-primary`
- **Badges**: `text-[10px] font-medium px-2 py-0.5 rounded-sm border` with semantic border color
- **Metric columns**: `divide-x divide-border-secondary` grid
- **Metric label**: `text-[10px] uppercase tracking-wider text-text-muted mb-1.5`
- **Metric value**: `text-[18px] font-semibold tabular-nums leading-none` colored by sign
- **Metric sub-value**: `text-[11px] text-text-muted mt-1.5 tabular-nums`
- **All padding**: `px-4 py-3` inside metric columns

### Options Chain Pattern
- Dense data grid with `CE | STRIKE | PE` columns
- Tiny OI bars (3px) below each row — subtle data viz
- ATM row: `border-l-2 border-l-loss bg-loss/5` — colored left accent
- Hover: `hover:bg-bg-hover transition-colors`

### Keyboard Shortcuts Modal
- Section headers: **colored uppercase** (brand green for category names)
- Clean two-column layout
- Key badges: `rounded bg-bg-tertiary px-2 py-0.5`
- Generous whitespace between sections

---

## Chunk 1: Fix PnLHeatmap to look like GitHub contributions

The heatmap must:
- Fill the container width (cells expand to use available space)
- Look like GitHub's contribution chart: small dense cells, minimal gaps, centered in container
- No chunky borders or oversized titles

### Task 1: Rewrite PnLHeatmap.tsx

**Files:**
- Rewrite: `frontend/src/components/PnLHeatmap.tsx`

- [ ] **Step 1: Responsive cell sizing**

Use `ResizeObserver` to measure container width. Compute cell size:
```
availableWidth = containerWidth - dayLabelWidth(24px)
cellSize = floor(availableWidth / totalColumns) - gap
clamp cellSize between 10px and 14px
```

Center the grid horizontally if it doesn't perfectly fill (use `mx-auto` on grid wrapper).

- [ ] **Step 2: Visual styling**

- Cell corners: `rounded-[1px]` (barely visible, like GitHub)
- Gap: `2px` between cells
- Empty color: `#222` (darker than bg, subtle)
- Profit colors: `rgba(76,175,80, 0.15/0.35/0.6/0.85)` (4 levels)
- Loss colors: `rgba(229,57,53, 0.15/0.35/0.6/0.85)` (4 levels)
- Month labels: `text-[9px] text-text-muted` above grid
- Day labels: `text-[9px] text-text-muted` left of grid (Mon/Wed/Fri only)
- Legend: inline with grid, left-aligned with grid start, `text-[9px]`
- Tooltip: `bg-bg-primary border border-border-primary rounded-sm px-2 py-1 text-xs` positioned above cell

- [ ] **Step 3: No wrapper chrome**

The component renders NO outer border, NO title, NO padding. The parent (Analytics.tsx) wraps it in a bordered card and provides the title. This keeps the component composable.

- [ ] **Step 4: Commit**

---

## Chunk 2: Rewrite Analytics.tsx with FII/DII-quality design

Every section follows the FII/DII card pattern: bordered card → header with title/badge → metric columns with large numbers.

**ALL sections render regardless of data.** When no trades exist, metric values show "—" and insight sections show centered muted empty-state text. The page structure is always fully visible.

### Task 2: Page structure and sections

**Files:**
- Rewrite: `frontend/src/pages/Analytics.tsx`

- [ ] **Step 1: Page layout (every section ALWAYS visible)**

```
┌────────────────────────────────────────────────────────────┐
│ Analytics                                    N trades  (h-9)│
╞════════════════════════════════════════════════════════════╡
│                                                            │
│ ╔═══════════════════════════════════════════════════════╗  │
│ ║ Performance                    [Strong Edge] badge   ║  │ Section 1
│ ╟──────────┬───────────┬───────────┬──────────────────╢  │ FII-style card
│ ║ NET P&L  │ WIN RATE  │EXPECTANCY │ RISK:REWARD      ║  │ 4-col divide-x
│ ║ +₹18.5K  │ 62.5%     │ +₹768     │ 1 : 1.58        ║  │ Large numbers
│ ║ unrl +₹0 │ 15W / 9L  │ per trade │ factor 1.58      ║  │ Sub values
│ ╚══════════╧═══════════╧═══════════╧══════════════════╝  │
│                                                            │
│ ╔═══════════════════════════════════════════════════════╗  │
│ ║ Equity Curve                                         ║  │ Section 2
│ ║ [custom SVG area chart, 140px tall, full width]      ║  │ bordered card
│ ╚══════════════════════════════════════════════════════╝  │
│                                                            │
│ ╔═══════════════════════════════════════════════════════╗  │
│ ║ P&L Heatmap                                          ║  │ Section 3
│ ║ [GitHub-style heatmap, responsive cells, full width] ║  │ bordered card
│ ╚══════════════════════════════════════════════════════╝  │
│                                                            │
│ ╔════════════════╦════════════════╦═════════════════════╗  │
│ ║ Your Edge      ║ Risk           ║ Behavior            ║  │ Section 4
│ ╟────────────────╫────────────────╫─────────────────────╢  │ 3 cards
│ ║ R:R    1:1.58  ║ Max DD  ₹3.2K ║ Win hold   2d       ║  │ FII-style
│ ║ PF     1.58    ║ Best   +₹4.2K ║ Loss hold  4h       ║  │ each with
│ ║                ║ Worst  -₹2.1K ║ [Letting winners run]║  │ header+body
│ ║                ║ Streaks 6W 3L ║                      ║  │
│ ╚════════════════╩════════════════╩═════════════════════╝  │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║ TRADE INSIGHTS                          section hdr  ║  │ Section 5
│ ║ ┌─────────┬─────────┬─────────┬────────────────────┐║  │ 4-col grid
│ ║ │ By Type │ By Dir  │By Money │ By Hold Duration   │║  │ of SlicePanels
│ ║ │ CE +12K │LONG +11K│OTM +8K │ Intraday  -1.2K    │║  │
│ ║ │ PE +6K  │SHRT +7K │ATM +7K │ 1-2 days  +5K      │║  │
│ ║ │         │         │ITM +3K │ 3-7 days  +10K     │║  │
│ ║ └─────────┴─────────┴─────────┴────────────────────┘║  │
│ ║ ┌─────────┬─────────┬─────────┬────────────────────┐║  │
│ ║ │ By DTE  │ By Size │ By VIX  │ By VIX Change      │║  │ Row 2
│ ║ └─────────┴─────────┴─────────┴────────────────────┘║  │
│ ║ ┌─────────┬─────────┬─────────┬────────────────────┐║  │
│ ║ │ By Day  │By Time  │By Spot  │ By Expiry Week     │║  │ Row 3
│ ║ └─────────┴─────────┴─────────┴────────────────────┘║  │
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║ BEHAVIORAL INSIGHTS                     section hdr  ║  │ Section 6
│ ║ ┌──────────────┬──────────────┬─────────────────────┐║  │ 3-col grid
│ ║ │▌Revenge Trade │ Overtrading  │▐Conviction Sizing  │║  │ accent borders
│ ║ │ 3 trades     │ Heavy: -₹800 │ Big: 70% WR        │║  │ + badges
│ ║ │ 25% WR       │ Light: +₹1.2K│ Small: 55% WR      │║  │
│ ║ ├──────────────┼──────────────┼─────────────────────┤║  │
│ ║ │▐Premium Captu│ Overnight Gap│                     │║  │
│ ║ │ Avg +22.4%   │ Helped 60%   │                     │║  │
│ ║ └──────────────┴──────────────┴─────────────────────┘║  │
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║ RECENT DAYS                             section hdr  ║  │ Section 7
│ ║ [HBarChart, last 15 days, full width bars]           ║  │ bordered card
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║ Trade Log                               card header  ║  │ Section 8
│ ╟──────────────────────────────────────────────────────╢  │ FII-style card
│ ║ Strike│CE/PE│Dir│Lots│Hold│DTE│Spot│VIX│P&L         ║  │ with table
│ ║ 23400 │ CE  │LONG│ 1 │ 2d │ 3d│23.4K│14│+₹2,762    ║  │
│ ║ 23200 │ PE  │SHRT│ 1 │ 3h │ 1d│23.2K│16│+₹1,475    ║  │
│ ╚══════════════════════════════════════════════════════╝   │
└────────────────────────────────────────────────────────────┘
```

- [ ] **Step 2: Section 1 — Performance Card**

Exactly like FII participant card:
```tsx
<div className="rounded border border-border-primary">
  {/* Header */}
  <div className="flex items-center justify-between px-4 py-3 border-b border-border-primary">
    <div className="flex items-center gap-2">
      <span className="text-[14px] font-semibold text-text-primary">Performance</span>
      <span className="text-[11px] text-text-muted">{wins}W / {losses}L</span>
    </div>
    <Badge label="Strong Edge" variant="profit" />  {/* or Marginal/No Edge */}
  </div>
  {/* Metrics — 4 columns like FUTURES|CALLS|PUTS */}
  <div className="grid grid-cols-4 divide-x divide-border-secondary">
    <MetricCol label="NET P&L" value="+₹18.5K" sub="Unrealised +₹0" className="text-profit" />
    <MetricCol label="WIN RATE" value="62.5%" sub="15W / 9L" className="text-profit" />
    <MetricCol label="EXPECTANCY" value="+₹768" sub="Per trade" className="text-profit" />
    <MetricCol label="RISK : REWARD" value="1 : 1.58" sub="Factor 1.58" />
  </div>
</div>
```

MetricCol component (px-4 py-3, label uppercase tracking-wider, value text-[18px] font-semibold, sub text-[11px] text-text-muted):
```tsx
function MetricCol({ label, value, sub, className }) {
  return (
    <div className="px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-text-muted mb-1.5">{label}</div>
      <div className={`text-[18px] font-semibold tabular-nums leading-none ${className}`}>{value}</div>
      {sub && <div className="text-[11px] text-text-muted mt-1.5 tabular-nums">{sub}</div>}
    </div>
  )
}
```

Badge component:
```tsx
function Badge({ label, variant }) {
  const cls = variant === 'profit' ? 'border-profit/40 text-profit'
    : variant === 'loss' ? 'border-loss/40 text-loss'
    : 'border-border-primary text-text-secondary'
  return <span className={`text-[10px] font-medium px-2 py-0.5 rounded-sm border ${cls}`}>{label}</span>
}
```

- [ ] **Step 3: Section 2 — Equity Curve**

Bordered card, uppercase label, EquityCurveSVG:
```tsx
<div className="rounded border border-border-primary p-4">
  <div className="text-[10px] uppercase tracking-wider text-text-muted mb-3">Equity Curve</div>
  <EquityCurveSVG data={equityCurve} height={140} />
</div>
```

Empty state handled by EquityCurveSVG internally.

- [ ] **Step 4: Section 3 — P&L Heatmap**

Bordered card wrapping the heatmap:
```tsx
<div className="rounded border border-border-primary p-4">
  <div className="text-[10px] uppercase tracking-wider text-text-muted mb-3">P&L Heatmap</div>
  <PnLHeatmap data={analytics?.pnl_by_day ?? []} />
</div>
```

- [ ] **Step 5: Section 4 — Edge + Risk + Behavior (3 cards)**

Three FII-style cards in `grid grid-cols-3 gap-4`:

**Card 1: Your Edge**
- Header: "Your Edge"
- 2-col grid: Risk:Reward | Profit Factor
- Large numbers colored by quality

**Card 2: Risk**
- Header: "Risk"
- 3-col grid: Max DD | Best Trade | Worst Trade
- Red for DD and worst, green for best

**Card 3: Behavior**
- Header: "Behavior" + badge "Letting winners run" (or "Cutting winners short")
- 2-col grid: Avg Win Hold | Avg Loss Hold
- Footer row: Streaks — `6W` green, `3L` red inline

All three always visible. When no trades, values show "—".

- [ ] **Step 6: Section 5 — Trade Insights**

Bordered card containing a 4-column grid of `SlicePanel` components. Each SlicePanel is inside a `rounded border border-border-secondary p-3` sub-card.

12 panels total in 3 rows of 4:
- Row 1: By Type, By Direction, By Moneyness, By Hold Duration
- Row 2: By Days to Expiry, By Size, By VIX Regime, By VIX Change
- Row 3: By Day of Week, By Time of Day, By Spot Move, By Expiry Week

Empty state: when no trades, show `"Trade insights will appear after your first closed trades"` centered muted text.

Panels with all-Unknown data are hidden (e.g. VIX unknown before we started storing it).

- [ ] **Step 7: Section 6 — Behavioral Insights**

Bordered card containing 3-column grid of insight cards.

Each insight card:
```tsx
<div className={`rounded border px-4 py-3 ${
  verdict === 'good' ? 'border-profit/30 bg-profit/5' :
  verdict === 'bad' ? 'border-loss/30 bg-loss/5' :
  'border-border-secondary'
}`}>
  <div className="flex items-center justify-between mb-1">
    <span className="text-[12px] font-medium text-text-primary">{label}</span>
    <Badge label="Good"/"Warning"/"Neutral" variant={...} />
  </div>
  <div className="text-[10px] text-text-muted mb-2">{description}</div>
  <div className="text-[12px] font-medium tabular-nums text-text-secondary">{value}</div>
</div>
```

Empty state: `"Behavioral patterns will be detected as you trade more"` centered muted.

- [ ] **Step 8: Section 7 — Recent Days**

Bordered card with HBarChart. Always visible (pnl_by_day from basic analytics).

- [ ] **Step 9: Section 8 — Trade Log**

FII-style card with header + table body:
```tsx
<div className="rounded border border-border-primary">
  <div className="px-4 py-2.5 border-b border-border-primary">
    <span className="text-[13px] font-semibold text-text-primary">Trade Log</span>
  </div>
  {trades.length > 0 ? (
    <table>...</table>  // Same pattern as Positions/History pages
  ) : (
    <div className="py-8 text-center text-xs text-text-muted">
      Your closed trades will appear here
    </div>
  )}
</div>
```

Table columns: Strike, CE/PE tag, Direction (colored LONG=green, SHORT=red), Lots, Hold, DTE, Spot at entry, VIX at entry, P&L (colored).

Table styling matches Positions page exactly:
- Headers: `px-4 py-[5px] font-normal text-[10px] uppercase tracking-wider text-text-muted`
- Rows: `border-b border-border-secondary/40 hover:bg-bg-hover transition-colors`
- Data: `px-4 py-1.5 tabular-nums`

- [ ] **Step 10: Data loading**

Fetch enriched analytics on page mount / portfolio change. Fall back to basic analytics from Zustand store for headline/curve/heatmap while loading. No 30s polling for enriched (it's heavy).

- [ ] **Step 11: Commit**

---

## Chunk 3: Redesign Funds Page

The Funds page currently uses the wrong design patterns (SVG icons, inline text layout). Redesign using the same FII/DII card pattern.

### Task 3: Rewrite Funds.tsx

**Files:**
- Rewrite: `frontend/src/pages/Funds.tsx`

- [ ] **Step 1: Layout**

```
┌────────────────────────────────────────────────────┐
│ Funds                                      (h-9)   │
╞════════════════════════════════════════════════════╡
│                                                    │
│ ╔═════════════════════════════════════════════════╗│
│ ║ Account Overview                               ║│  FII-style card
│ ╟──────────┬───────────┬──────────────────────────╢│
│ ║ EQUITY   │ P&L       │ AVAILABLE MARGIN         ║│  3-col
│ ║ ₹5.0L    │ +₹18.5K   │ ₹4.82L                   ║│  Large numbers
│ ║ total    │ realised   │ margin available          ║│
│ ╚══════════╧═══════════╧══════════════════════════╝│
│                                                    │
│ ╔═════════════════════════════════════════════════╗│
│ ║ Fund Breakdown                    card header   ║│  FII-style card
│ ╟─────────────────────────────────────────────────╢│  with table
│ ║ Cash Balance              ₹5,00,000.00          ║│
│ ║ Blocked Margin            ₹0.00                 ║│
│ ║ Blocked Premium           ₹0.00                 ║│
│ ║ Available Funds           ₹5,00,000.00          ║│
│ ║ Realised P&L              +₹0.00                ║│
│ ║ Unrealised P&L            +₹0.00                ║│
│ ║ Total Equity              ₹5,00,000.00          ║│
│ ╚═════════════════════════════════════════════════╝│
└────────────────────────────────────────────────────┘
```

- [ ] **Step 2: Implement with FII card patterns**

Account Overview card: bordered card with header + 3-column metric grid.
Fund Breakdown card: bordered card with header + table (same pattern as current but with proper card wrapping).

- [ ] **Step 3: Commit**

---

## Chunk 4: Cleanup

### Task 4: Restore vite proxy to production

**Files:**
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Change proxy targets back**

```typescript
proxy: {
  '/api/v1/ws': { target: 'wss://lite-options-api-production.up.railway.app', ws: true },
  '/api': { target: 'https://lite-options-api-production.up.railway.app', changeOrigin: true },
},
```

- [ ] **Step 2: Commit**

### Task 5: Smoke test all pages

- [ ] Navigate every route: Dashboard, Positions, Orders, History, Funds, Analytics, Settings
- [ ] Verify no regressions
- [ ] Take screenshots of Analytics and Funds for review

### Task 6: Deploy backend changes

- [ ] Push backend to Railway (or whatever deployment mechanism)
- [ ] Verify `/api/v1/analytics/enriched` works in production
- [ ] Deploy frontend

---

## Design Rules (non-negotiable)

1. **Every card** uses `rounded border border-border-primary` — NOT just `bg-bg-secondary`
2. **Card headers** always have `border-b border-border-primary` separator
3. **Metric values** are `text-[18px] font-semibold tabular-nums` — big and prominent
4. **Metric labels** are `text-[10px] uppercase tracking-wider text-text-muted`
5. **Multi-column metrics** use `divide-x divide-border-secondary` — NOT separate cards
6. **Badges** for verdicts: bordered pills with semantic color
7. **Tables** match Positions/History page exactly
8. **Empty states** are always visible — never hide sections behind data gates
9. **No Sharpe/Sortino/Calmar** — removed per user request, not useful for this trading style
10. **No lightweight-charts** on analytics page — custom SVG only
11. **Heatmap** must fill container width with small dense cells like GitHub contributions
12. **Color only signals meaning** — green for profit/good, red for loss/bad, never decorative
