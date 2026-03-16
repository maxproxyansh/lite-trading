# Drawings & Indicators — Design Spec

## Overview

Add drawing tools and technical indicators to the NiftyChart component. The system must be powerful and comprehensive while keeping the default chart experience completely clean and uncluttered. All features are hidden behind two small toggle buttons in the existing header bar.

Works identically for NIFTY 50 spot and option charts.

## Scope

### Drawing Tools (7)

| Tool | Points | Description |
|------|--------|-------------|
| Horizontal line | 1 (price) | Full-width price level line |
| Vertical line | 1 (time) | Full-height time marker |
| Trend line | 2 | Line segment between two price-time points |
| Channel | 2 + drag | Parallel trend lines with optional fill |
| Rectangle | 2 (corners) | Filled rectangular zone |
| Fib retracement | 2 | Horizontal levels at 0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0 |
| Measure / price range | 2 | Shows price diff, percentage, and bar count |

### Indicators (9)

**Overlay (main chart):**

| Indicator | Default Params | Series Type |
|-----------|---------------|-------------|
| EMA | period: 21 | Line |
| SMA | period: 50 | Line |
| Bollinger Bands | period: 20, stdDev: 2 | 3 lines + area fill |
| VWAP | — | Line |
| Supertrend | period: 10, multiplier: 3 | Line (color changes on direction) |
| Ichimoku | tenkan: 9, kijun: 26, senkou: 52 | 5 lines + cloud fill |

**Oscillator (sub-pane):**

| Indicator | Default Params | Series Type |
|-----------|---------------|-------------|
| RSI | period: 14 | Line + 30/70 reference lines |
| MACD | fast: 12, slow: 26, signal: 9 | 2 lines + histogram |
| ADX | period: 14 | 3 lines (ADX, +DI, -DI) |

## Persistence

### Local-first, backend-sync-ready

All state persisted to localStorage with a serialization format designed for easy future migration to a backend API.

**Drawings:** Stored per-symbol under key `drawings:{symbol}`.

```typescript
type DrawingPoint = { time: number; price: number }
// time is stored as IST-shifted UTC timestamp (raw_utc + IST_OFFSET_SECONDS),
// matching the chart's internal time axis. This avoids conversion on every render
// frame. For future backend sync, subtract IST_OFFSET_SECONDS to get true UTC.

type Drawing = {
  id: string                    // crypto.randomUUID()
  type: 'hline' | 'vline' | 'trendline' | 'channel' | 'rectangle' | 'fib' | 'measure'
  points: DrawingPoint[]        // IST-shifted timestamps + prices
  style: {
    color: string               // hex
    lineWidth: 1 | 2 | 3
    lineStyle: 'solid' | 'dashed' | 'dotted'
    fillOpacity?: number        // for rect, channel, fib zones (0-1)
  }
  createdAt: number
}
```

**Timestamp convention:** Drawing timestamps are stored IST-shifted (same as chart candle timestamps: `raw_utc + IST_OFFSET_SECONDS`). This means `timeToCoordinate()` works directly without conversion. For future backend sync, the drawing manager would subtract the IST offset before sending to the server.

**Symbol isolation:** Drawings for "NIFTY 50" (spot) are completely separate from drawings for "NIFTY 24500 CE" (option). Each symbol has its own independent drawing set. This matches how alerts are already scoped.

All coordinates use absolute price-time values, never candle indices or pixels. This ensures drawings render correctly across all timeframes.

**Indicator config:** Stored globally under key `indicators:config`.

```typescript
type IndicatorConfig = {
  id: string                    // crypto.randomUUID() — allows multiple instances of same type in v2
  type: 'ema' | 'sma' | 'bb' | 'vwap' | 'supertrend' | 'ichimoku' | 'rsi' | 'macd' | 'adx'
  enabled: boolean
  params: Record<string, number>
  color: string
  lineWidth: 1 | 2
}
```

**Sync:** localStorage writes debounced at 500ms after last change. No write on every drag frame.

## UI Design

### Entry Points

Two buttons added to the existing chart header bar, next to Vol and Alerts:

- **"Draw"** button — toggles the drawing toolbar
- **"Indicators"** button — toggles the indicator dropdown panel

When neither is active, the chart looks exactly as it does today. Zero visual change for users who don't use these features.

### Drawing Toolbar

- 36px vertical strip on the left edge of the chart, overlaying the chart canvas (does not push it)
- Contains 7 tool icons + trash/delete-all at bottom
- Icon-only, no labels. Tooltips on hover.
- Active tool highlighted with brand color border/background
- Status hint text at top-left of chart: "Horizontal Line tool active — click chart to place"
- Press Escape or click "Draw" again to dismiss toolbar
- Mobile: icons scale to 44px touch targets

### Indicator Dropdown Panel

- Floating dropdown anchored to the "Indicators" button
- Two sections: "Overlay" and "Oscillator", separated by divider
- Each indicator is a toggle chip — click to enable/disable
- Active indicators show checkmark and brand color highlight
- Click outside to dismiss
- Future: gear icon per chip for parameter configuration

### Oscillator Sub-Panes

- Stack below the main chart canvas
- Main chart is `flex-1` — it shrinks automatically as panes expand
- Each pane has a thin header (22px): collapse toggle, name, period, current value, remove button
- Collapsed: 22px strip showing just the live indicator value
- Expanded: 22px header + ~80px chart area
- Each pane is a separate `createChart()` instance with synced time scale

## Rendering Architecture

### Drawings — lightweight-charts Plugin API

Each drawing type is a plugin class implementing `ISeriesPrimitivePaneView`:

```
BaseDrawingPlugin (abstract)
  ├── HorizontalLinePlugin
  ├── VerticalLinePlugin
  ├── TrendLinePlugin
  ├── ChannelPlugin
  ├── RectanglePlugin
  ├── FibRetracementPlugin
  └── MeasurePlugin
```

Plugins implement `ISeriesPrimitivePaneView` with a `renderer()` that returns an object with a `draw(target: CanvasRenderingTarget2D)` method. The `target` (from `fancy-canvas`) is NOT a raw `CanvasRenderingContext2D` — call `target.useMediaCoordinateSpace(scope => { scope.context... })` to get the actual 2D context. Use media coordinate space (not bitmap) because `priceToCoordinate()` / `timeToCoordinate()` return media coordinates.

**Coordinate access:** Plugins receive chart/series refs through the `attached(param: SeriesAttachedParameter)` lifecycle hook, which provides `param.chart` (for `chart.timeScale().timeToCoordinate()`) and `param.series` (for `series.priceToCoordinate()`). The base drawing class must store these refs in `attached()` and clear them in `detached()`. The `draw()` method converts the drawing's IST-shifted `{time, price}` points to pixel coordinates using these refs on every frame. Pan/zoom/timeframe changes work automatically.

### Overlay Indicators — Line Series

Each overlay indicator adds `LineSeries` to the main chart:
- EMA/SMA: 1 line series
- Bollinger: 3 line series + fill between upper/lower via two stacked area series (upper area with transparent bottom, lower area with transparent top — visual overlap creates the fill). Note: fill inverts when bands cross, which is acceptable as BB crossover is a rare extreme event
- VWAP: 1 line series
- Supertrend: 2 line series (bullish green, bearish red) with gaps where the other is active — `LineSeries` does not support per-point colors
- Ichimoku: 5 line series + cloud fill via same stacked area technique as Bollinger (Senkou Span A and B). Cloud color changes based on which span is on top (green when A > B, red when B > A)

Series refs stored in `Map<string, ISeriesApi[]>` keyed by indicator id.

### Oscillator Indicators — Separate Chart Instances

Each oscillator gets its own `createChart()` below the main chart:
- Time scale synced one-directionally: main chart → oscillator only. Main chart's `subscribeVisibleLogicalRangeChange` calls `oscillatorChart.timeScale().setVisibleLogicalRange()`. Oscillator charts do NOT sync back to main — this prevents feedback loops. A boolean guard flag (`isSyncing`) prevents re-entrancy if oscillator range-change events fire during sync.
- RSI: line series + horizontal reference lines at 30/70 + overbought/oversold background zones
- MACD: 2 line series (MACD line, signal line) + histogram series
- ADX: 3 line series (ADX, +DI, -DI)

### Interaction — DOM Overlay for Handles

Drawing interaction uses a thin DOM overlay for drag handles and selection:

- **Hover detection**: On `mousemove`, check proximity to drawing anchor points / edges
- **Selection**: Click drawing → show anchor handles (small circles). Subtle glow on selected drawing.
- **Drag anchors**: Resize/reshape the drawing
- **Drag edge**: Move entire drawing (all points shift by same delta)
- **Right-click / long-press**: Context popover for color, line width, line style, delete
- **Mobile**: Long-press to select + show context menu. Same drag gestures.

## Interaction State Machine

```
IDLE
  ├─ click tool ──→ PLACING
  │                   ├─ click chart (point 1)
  │                   │   ├─ single-point tool (hline/vline) ──→ COMMITTED → IDLE
  │                   │   └─ multi-point tool ──→ click chart (point 2) ──→ COMMITTED → IDLE
  │                   │       (channel: point 2 then drag for width)
  │                   ├─ Escape ──→ IDLE
  │                   └─ right-click ──→ IDLE
  │
  ├─ click existing drawing ──→ SELECTED
  │                               ├─ drag anchor ──→ DRAGGING → release → SELECTED
  │                               ├─ drag edge ──→ MOVING → release → SELECTED
  │                               ├─ right-click / long-press ──→ CONTEXT_MENU
  │                               │   ├─ change style → SELECTED
  │                               │   └─ delete → IDLE
  │                               ├─ Delete/Backspace ──→ IDLE (drawing removed)
  │                               ├─ Escape ──→ IDLE (deselect)
  │                               └─ click empty area ──→ IDLE
  │
  └─ click empty chart ──→ IDLE (no-op)
```

## Drawing vs Alert Interaction Priority

The chart has an existing alert line system (DOM overlay with drag). Drawings must coexist:

- **Drawing tool active** (`activeTool !== null`): All clicks go to the drawing system. Alert hover/select/drag is suppressed. Alerts still render visually but are not interactive.
- **No tool active, drawing toolbar open**: Clicks near existing drawings → select drawing. Clicks near alert lines → select alert. Drawings take priority if both overlap at the same point (drawings are user-created and more likely the intended target).
- **Drawing toolbar closed**: Alert system works exactly as today. Drawing selection is disabled — drawings still render but are not interactive.

## Cleanup & Lifecycle

The `IndicatorManager` must call `chart.remove()` on all oscillator chart instances when:
- The main chart unmounts
- Symbol changes (oscillator data is recomputed, charts may be recreated)
- All oscillator indicators are disabled

The `DrawingManager` must call `detached()` on all active plugins and clear refs on unmount. Both managers are destroyed in the main chart's `useEffect` cleanup. Order: destroy oscillator panes first (they depend on main chart for sync), then drawing plugins, then main chart.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `-` | Horizontal line tool |
| `\|` (Shift+\\) | Vertical line tool |
| `T` | Trend line tool |
| `Delete` / `Backspace` | Delete selected drawing |
| `Escape` | Cancel placement / deselect |

## State Management

### New Zustand Slices

```typescript
// Drawing state
drawingToolbar: boolean
activeTool: DrawingType | null
drawings: Record<string, Drawing[]>     // symbol → drawings (Record, not Map — JSON-serializable)
selectedDrawingId: string | null
drawingInProgress: DrawingPoint[] | null

// Indicator state
indicatorPanelOpen: boolean
indicators: IndicatorConfig[]
oscillatorPaneState: Record<string, boolean> // indicatorId → expanded (Record, not Map)
```

Note: `Record` (plain object) is used instead of `Map` for Zustand compatibility — `Map` is not JSON-serializable and breaks `useShallow` equality checks. The existing store exclusively uses plain objects and arrays.

### Manager Classes (Imperative, Not React)

**DrawingManager** — instantiated once when chart mounts:
- CRUD drawings, attach/detach plugins to chart
- Hit-testing for hover/selection
- Coordinate conversion for interaction
- localStorage sync (debounced)

**IndicatorManager** — instantiated once when chart mounts:
- Add/remove line series for overlay indicators
- Create/destroy sub-chart instances for oscillators
- Recompute indicator data when candles change
- Cache computed results, invalidate on candle data change

Both receive chart/series refs and operate imperatively. This avoids React re-render overhead for canvas operations.

## File Structure

```
src/
├── components/
│   ├── NiftyChart.tsx                  ← add toolbar/indicator toggle buttons + pane layout
│   ├── chart/
│   │   ├── DrawingToolbar.tsx          ← 36px vertical toolbar
│   │   ├── DrawingContextMenu.tsx      ← right-click popover
│   │   ├── IndicatorPanel.tsx          ← dropdown with toggle chips
│   │   ├── OscillatorPane.tsx          ← single oscillator sub-chart
│   │   └── IndicatorLegend.tsx         ← overlay labels for active overlays
│   └── ...
├── lib/
│   ├── chart/
│   │   ├── plugins/
│   │   │   ├── base-drawing.ts         ← abstract base: coords, hit-test, render helpers
│   │   │   ├── hline.ts
│   │   │   ├── vline.ts
│   │   │   ├── trendline.ts
│   │   │   ├── channel.ts
│   │   │   ├── rectangle.ts
│   │   │   ├── fib-retracement.ts
│   │   │   └── measure.ts
│   │   ├── indicators/
│   │   │   ├── ema.ts
│   │   │   ├── sma.ts
│   │   │   ├── bollinger.ts
│   │   │   ├── vwap.ts
│   │   │   ├── supertrend.ts
│   │   │   ├── ichimoku.ts
│   │   │   ├── rsi.ts
│   │   │   ├── macd.ts
│   │   │   └── adx.ts
│   │   ├── drawing-manager.ts
│   │   └── indicator-manager.ts
│   └── ...
└── store/
    └── useStore.ts                     ← add drawing + indicator slices
```

## Indicator Computation

All indicators are pure functions: `Candle[] + params → series data[]`. Computed client-side from `rawCandlesRef` (already available). No new backend API calls.

Recomputation triggers:
- Timeframe change (new candle data loaded)
- New candles fetched (pagination / history load)
- Live candle update (recompute last N values, not full recalc)
- Indicator params changed by user

## Cross-Timeframe Drawing Behavior

All drawings are stored as absolute `{time: IST_shifted_timestamp, price: number}` coordinates. When the chart displays a different timeframe, the drawing plugin simply converts these absolute coordinates to the current chart's pixel space. A horizontal line at price 24,500 renders at 24,500 on every timeframe. A trendline between two time-price points maps correctly regardless of which candles are visible.

## Mobile Considerations

- Drawing toolbar: 44px touch targets (vs 36px desktop)
- Long-press on drawing: select + open context menu
- Drag gestures: same as desktop pointer, touch-aware thresholds (12px vs 5px)
- Indicator dropdown: full-width on mobile (< 600px)
- Oscillator panes: same behavior, slightly taller touch targets on headers

## Out of Scope (Future)

- Backend sync for drawings (designed for, not built)
- Indicator parameter configuration UI (chips toggle on/off only; config comes in v2)
- Multiple instances of same indicator (e.g. EMA 9 + EMA 21 simultaneously) — v2, but UUID-based indicator IDs mean no data migration needed
- Drawing templates / favorites
- Undo/redo
