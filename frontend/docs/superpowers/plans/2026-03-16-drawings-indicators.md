# Drawings & Indicators Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 7 drawing tools and 9 technical indicators to the NiftyChart, hidden behind two toggle buttons in the header bar.

**Architecture:** Drawing plugins render on the chart canvas via lightweight-charts plugin API. Overlay indicators use LineSeries on the main chart. Oscillator indicators get separate synced chart instances below the main chart. All state managed via Zustand with localStorage persistence.

**Tech Stack:** lightweight-charts v4.2.3 (plugin API, fancy-canvas), React 19, Zustand 5, TypeScript, Tailwind CSS 4

**Spec:** `docs/superpowers/specs/2026-03-16-drawings-indicators-design.md`

**Note:** No test framework exists in this frontend project. Steps use TypeScript compile checks (`npx tsc --noEmit`) and visual verification in the browser instead of unit tests.

---

## Chunk 1: Foundation — Types, Store Slices, Persistence

### Task 1: Shared Type Definitions

**Files:**
- Create: `src/lib/chart/types.ts`

- [ ] **Step 1: Create type definitions file**

```typescript
// src/lib/chart/types.ts

export type DrawingType = 'hline' | 'vline' | 'trendline' | 'channel' | 'rectangle' | 'fib' | 'measure'

export type DrawingPoint = {
  time: number   // IST-shifted UTC timestamp (raw_utc + IST_OFFSET_SECONDS)
  price: number
}

export type DrawingStyle = {
  color: string           // hex e.g. '#6366f1'
  lineWidth: 1 | 2 | 3
  lineStyle: 'solid' | 'dashed' | 'dotted'
  fillOpacity?: number    // 0-1, for rect/channel/fib zones
}

export type Drawing = {
  id: string              // crypto.randomUUID()
  type: DrawingType
  points: DrawingPoint[]
  style: DrawingStyle
  createdAt: number
}

export type IndicatorType = 'ema' | 'sma' | 'bb' | 'vwap' | 'supertrend' | 'ichimoku' | 'rsi' | 'macd' | 'adx'

export type IndicatorConfig = {
  id: string              // crypto.randomUUID()
  type: IndicatorType
  enabled: boolean
  params: Record<string, number>
  color: string
  lineWidth: 1 | 2
}

export const OVERLAY_INDICATORS: IndicatorType[] = ['ema', 'sma', 'bb', 'vwap', 'supertrend', 'ichimoku']
export const OSCILLATOR_INDICATORS: IndicatorType[] = ['rsi', 'macd', 'adx']

export const DEFAULT_DRAWING_STYLE: DrawingStyle = {
  color: '#6366f1',
  lineWidth: 1,
  lineStyle: 'solid',
  fillOpacity: 0.1,
}

export const DEFAULT_INDICATOR_CONFIGS: IndicatorConfig[] = [
  { id: crypto.randomUUID(), type: 'ema', enabled: false, params: { period: 21 }, color: '#f59e0b', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'sma', enabled: false, params: { period: 50 }, color: '#8b5cf6', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'bb', enabled: false, params: { period: 20, stdDev: 2 }, color: '#6366f1', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'vwap', enabled: false, params: {}, color: '#ec4899', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'supertrend', enabled: false, params: { period: 10, multiplier: 3 }, color: '#4caf50', lineWidth: 2 },
  { id: crypto.randomUUID(), type: 'ichimoku', enabled: false, params: { tenkan: 9, kijun: 26, senkou: 52 }, color: '#06b6d4', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'rsi', enabled: false, params: { period: 14 }, color: '#f59e0b', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'macd', enabled: false, params: { fast: 12, slow: 26, signal: 9 }, color: '#6366f1', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'adx', enabled: false, params: { period: 14 }, color: '#06b6d4', lineWidth: 1 },
]
```

- [ ] **Step 2: Verify types compile**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit`
Expected: clean, no errors

- [ ] **Step 3: Commit**

```bash
git add src/lib/chart/types.ts
git commit -m "feat: add shared type definitions for drawings and indicators"
```

### Task 2: localStorage Persistence Helpers

**Files:**
- Create: `src/lib/chart/storage.ts`

- [ ] **Step 1: Create storage helpers**

```typescript
// src/lib/chart/storage.ts
import type { Drawing, IndicatorConfig } from './types'
import { DEFAULT_INDICATOR_CONFIGS } from './types'

const DRAWING_KEY_PREFIX = 'drawings:'
const INDICATOR_KEY = 'indicators:config'

export function loadDrawings(symbol: string): Drawing[] {
  try {
    const raw = localStorage.getItem(`${DRAWING_KEY_PREFIX}${symbol}`)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function saveDrawings(symbol: string, drawings: Drawing[]): void {
  localStorage.setItem(`${DRAWING_KEY_PREFIX}${symbol}`, JSON.stringify(drawings))
}

export function loadIndicatorConfigs(): IndicatorConfig[] {
  try {
    const raw = localStorage.getItem(INDICATOR_KEY)
    return raw ? JSON.parse(raw) : structuredClone(DEFAULT_INDICATOR_CONFIGS)
  } catch {
    return structuredClone(DEFAULT_INDICATOR_CONFIGS)
  }
}

export function saveIndicatorConfigs(configs: IndicatorConfig[]): void {
  localStorage.setItem(INDICATOR_KEY, JSON.stringify(configs))
}

let saveDrawingsTimer: ReturnType<typeof setTimeout> | null = null
export function saveDrawingsDebounced(symbol: string, drawings: Drawing[]): void {
  if (saveDrawingsTimer) clearTimeout(saveDrawingsTimer)
  saveDrawingsTimer = setTimeout(() => saveDrawings(symbol, drawings), 500)
}

let saveIndicatorsTimer: ReturnType<typeof setTimeout> | null = null
export function saveIndicatorConfigsDebounced(configs: IndicatorConfig[]): void {
  if (saveIndicatorsTimer) clearTimeout(saveIndicatorsTimer)
  saveIndicatorsTimer = setTimeout(() => saveIndicatorConfigs(configs), 500)
}
```

- [ ] **Step 2: Verify compile**

Run: `npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add src/lib/chart/storage.ts
git commit -m "feat: add localStorage persistence helpers for drawings and indicators"
```

### Task 3: Zustand Store Slices

**Files:**
- Modify: `src/store/useStore.ts`

- [ ] **Step 1: Add imports and drawing/indicator state to the store interface**

At the top of `useStore.ts`, add import for the new types. In the `AppState` interface (around line 70), add:

```typescript
// Drawing state
drawingToolbar: boolean
activeTool: DrawingType | null
drawings: Record<string, Drawing[]>
selectedDrawingId: string | null
drawingInProgress: DrawingPoint[] | null

// Indicator state
indicatorPanelOpen: boolean
indicators: IndicatorConfig[]
oscillatorPaneState: Record<string, boolean>
```

- [ ] **Step 2: Add setter functions in the store create block**

Before the store closing (around line 608), add setters:

```typescript
// Drawing actions
setDrawingToolbar: (open: boolean) => set({ drawingToolbar: open, activeTool: open ? null : get().activeTool }),
setActiveTool: (tool: DrawingType | null) => set({ activeTool: tool, selectedDrawingId: null, drawingInProgress: null }),
setSelectedDrawingId: (id: string | null) => set({ selectedDrawingId: id }),
setDrawingInProgress: (points: DrawingPoint[] | null) => set({ drawingInProgress: points }),
addDrawing: (symbol: string, drawing: Drawing) => {
  const current = get().drawings[symbol] ?? []
  set({ drawings: { ...get().drawings, [symbol]: [...current, drawing] } })
  saveDrawingsDebounced(symbol, [...current, drawing])
},
updateDrawing: (symbol: string, id: string, updates: Partial<Drawing>) => {
  const current = get().drawings[symbol] ?? []
  const updated = current.map((d) => (d.id === id ? { ...d, ...updates } : d))
  set({ drawings: { ...get().drawings, [symbol]: updated } })
  saveDrawingsDebounced(symbol, updated)
},
removeDrawing: (symbol: string, id: string) => {
  const current = get().drawings[symbol] ?? []
  const filtered = current.filter((d) => d.id !== id)
  set({ drawings: { ...get().drawings, [symbol]: filtered }, selectedDrawingId: null })
  saveDrawingsDebounced(symbol, filtered)
},
clearDrawings: (symbol: string) => {
  set({ drawings: { ...get().drawings, [symbol]: [] }, selectedDrawingId: null })
  saveDrawings(symbol, [])
},
loadDrawingsForSymbol: (symbol: string) => {
  if (get().drawings[symbol]) return
  set({ drawings: { ...get().drawings, [symbol]: loadDrawings(symbol) } })
},

// Indicator actions
setIndicatorPanelOpen: (open: boolean) => set({ indicatorPanelOpen: open }),
toggleIndicator: (id: string) => {
  const indicators = get().indicators.map((ind) =>
    ind.id === id ? { ...ind, enabled: !ind.enabled } : ind
  )
  set({ indicators })
  saveIndicatorConfigsDebounced(indicators)
},
setOscillatorPaneExpanded: (id: string, expanded: boolean) => {
  set({ oscillatorPaneState: { ...get().oscillatorPaneState, [id]: expanded } })
},
```

- [ ] **Step 3: Add initial state values in the create block**

In the initial state object:

```typescript
drawingToolbar: false,
activeTool: null,
drawings: {},
selectedDrawingId: null,
drawingInProgress: null,
indicatorPanelOpen: false,
indicators: loadIndicatorConfigs(),
oscillatorPaneState: {},
```

- [ ] **Step 4: Verify compile**

Run: `npx tsc --noEmit`

- [ ] **Step 5: Commit**

```bash
git add src/store/useStore.ts
git commit -m "feat: add drawing and indicator state slices to Zustand store"
```

---

## Chunk 2: Drawing Plugin System

### Task 4: Base Drawing Plugin

**Files:**
- Create: `src/lib/chart/plugins/base-drawing.ts`

- [ ] **Step 1: Create the abstract base plugin class**

This class implements the lightweight-charts series primitive interface. It stores chart/series refs from `attached()`, provides coordinate conversion helpers, and defines the abstract `drawOnCanvas()` method that subclasses implement.

```typescript
// src/lib/chart/plugins/base-drawing.ts
import type {
  IChartApi,
  ISeriesApi,
  ISeriesPrimitive,
  ISeriesPrimitivePaneRenderer,
  ISeriesPrimitivePaneView,
  SeriesAttachedParameter,
  Time,
} from 'lightweight-charts'
import type { CanvasRenderingTarget2D } from 'fancy-canvas'
import type { Drawing, DrawingPoint } from '../types'

export abstract class BaseDrawingPlugin implements ISeriesPrimitive<Time> {
  drawing: Drawing
  protected _chart: IChartApi | null = null
  protected _series: ISeriesApi<'Candlestick'> | null = null
  private _paneViews: ISeriesPrimitivePaneView[] = []

  constructor(drawing: Drawing) {
    this.drawing = drawing
    this._paneViews = [new DrawingPaneView(this)]
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this._chart = param.chart
    this._series = param.series as ISeriesApi<'Candlestick'>
  }

  detached(): void {
    this._chart = null
    this._series = null
  }

  paneViews(): ISeriesPrimitivePaneView[] {
    return this._paneViews
  }

  updateDrawing(drawing: Drawing): void {
    this.drawing = drawing
  }

  /** Convert a DrawingPoint to pixel coordinates. Returns null if off-screen. */
  protected pointToPixel(point: DrawingPoint): { x: number; y: number } | null {
    if (!this._chart || !this._series) return null
    const x = this._chart.timeScale().timeToCoordinate(point.time as Time)
    const y = this._series.priceToCoordinate(point.price)
    if (x === null || y === null) return null
    return { x, y }
  }

  /** Convert a price to y pixel. Returns null if off-screen. */
  protected priceToY(price: number): number | null {
    if (!this._series) return null
    return this._series.priceToCoordinate(price)
  }

  /** Convert a time to x pixel. Returns null if off-screen. */
  protected timeToX(time: number): number | null {
    if (!this._chart) return null
    return this._chart.timeScale().timeToCoordinate(time as Time)
  }

  /** Get the line dash pattern for the drawing's lineStyle */
  protected getLineDash(): number[] {
    switch (this.drawing.style.lineStyle) {
      case 'dashed': return [6, 4]
      case 'dotted': return [2, 3]
      default: return []
    }
  }

  /** Subclasses implement this to draw on the canvas */
  abstract drawOnCanvas(ctx: CanvasRenderingContext2D, width: number, height: number): void
}

class DrawingPaneView implements ISeriesPrimitivePaneView {
  private _plugin: BaseDrawingPlugin

  constructor(plugin: BaseDrawingPlugin) {
    this._plugin = plugin
  }

  renderer(): ISeriesPrimitivePaneRenderer | null {
    return new DrawingPaneRenderer(this._plugin)
  }
}

class DrawingPaneRenderer implements ISeriesPrimitivePaneRenderer {
  private _plugin: BaseDrawingPlugin

  constructor(plugin: BaseDrawingPlugin) {
    this._plugin = plugin
  }

  draw(target: CanvasRenderingTarget2D): void {
    target.useMediaCoordinateSpace(({ context, mediaSize }) => {
      this._plugin.drawOnCanvas(context, mediaSize.width, mediaSize.height)
    })
  }
}
```

- [ ] **Step 2: Verify compile**

Run: `npx tsc --noEmit`

Note: `fancy-canvas` types come from `node_modules/fancy-canvas`. If the import fails, check `node_modules/lightweight-charts/node_modules/fancy-canvas` and adjust the import path or add to tsconfig paths.

- [ ] **Step 3: Commit**

```bash
git add src/lib/chart/plugins/base-drawing.ts
git commit -m "feat: add base drawing plugin with coordinate conversion helpers"
```

### Task 5: Horizontal Line Plugin

**Files:**
- Create: `src/lib/chart/plugins/hline.ts`

- [ ] **Step 1: Create horizontal line plugin**

```typescript
// src/lib/chart/plugins/hline.ts
import { BaseDrawingPlugin } from './base-drawing'

export class HorizontalLinePlugin extends BaseDrawingPlugin {
  drawOnCanvas(ctx: CanvasRenderingContext2D, width: number, _height: number): void {
    const y = this.priceToY(this.drawing.points[0].price)
    if (y === null) return

    ctx.beginPath()
    ctx.strokeStyle = this.drawing.style.color
    ctx.lineWidth = this.drawing.style.lineWidth
    ctx.setLineDash(this.getLineDash())
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()
    ctx.setLineDash([])

    // Price label on right edge
    const label = this.drawing.points[0].price.toFixed(2)
    ctx.font = '10px -apple-system, system-ui, sans-serif'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = this.drawing.style.color
    ctx.fillText(label, width - 4, y - 8)
  }
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/plugins/hline.ts
git commit -m "feat: add horizontal line drawing plugin"
```

### Task 6: Vertical Line Plugin

**Files:**
- Create: `src/lib/chart/plugins/vline.ts`

- [ ] **Step 1: Create vertical line plugin**

```typescript
// src/lib/chart/plugins/vline.ts
import { BaseDrawingPlugin } from './base-drawing'

export class VerticalLinePlugin extends BaseDrawingPlugin {
  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, height: number): void {
    const x = this.timeToX(this.drawing.points[0].time)
    if (x === null) return

    ctx.beginPath()
    ctx.strokeStyle = this.drawing.style.color
    ctx.lineWidth = this.drawing.style.lineWidth
    ctx.setLineDash(this.getLineDash())
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()
    ctx.setLineDash([])
  }
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/plugins/vline.ts
git commit -m "feat: add vertical line drawing plugin"
```

### Task 7: Trend Line Plugin

**Files:**
- Create: `src/lib/chart/plugins/trendline.ts`

- [ ] **Step 1: Create trend line plugin**

```typescript
// src/lib/chart/plugins/trendline.ts
import { BaseDrawingPlugin } from './base-drawing'

export class TrendLinePlugin extends BaseDrawingPlugin {
  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    if (this.drawing.points.length < 2) return
    const p1 = this.pointToPixel(this.drawing.points[0])
    const p2 = this.pointToPixel(this.drawing.points[1])
    if (!p1 || !p2) return

    ctx.beginPath()
    ctx.strokeStyle = this.drawing.style.color
    ctx.lineWidth = this.drawing.style.lineWidth
    ctx.setLineDash(this.getLineDash())
    ctx.moveTo(p1.x, p1.y)
    ctx.lineTo(p2.x, p2.y)
    ctx.stroke()
    ctx.setLineDash([])
  }
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/plugins/trendline.ts
git commit -m "feat: add trend line drawing plugin"
```

### Task 8: Channel Plugin

**Files:**
- Create: `src/lib/chart/plugins/channel.ts`

- [ ] **Step 1: Create channel plugin**

A channel has 3 points: two define the baseline, the third defines the offset (distance to the parallel line). We use the perpendicular distance from point 3 to the baseline.

```typescript
// src/lib/chart/plugins/channel.ts
import { BaseDrawingPlugin } from './base-drawing'

export class ChannelPlugin extends BaseDrawingPlugin {
  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    if (this.drawing.points.length < 3) return
    const p1 = this.pointToPixel(this.drawing.points[0])
    const p2 = this.pointToPixel(this.drawing.points[1])
    const p3 = this.pointToPixel(this.drawing.points[2])
    if (!p1 || !p2 || !p3) return

    // Perpendicular offset from baseline to p3
    const dx = p2.x - p1.x
    const dy = p2.y - p1.y
    const len = Math.sqrt(dx * dx + dy * dy)
    if (len === 0) return
    const nx = -dy / len
    const ny = dx / len
    const offset = (p3.x - p1.x) * nx + (p3.y - p1.y) * ny

    ctx.strokeStyle = this.drawing.style.color
    ctx.lineWidth = this.drawing.style.lineWidth
    ctx.setLineDash(this.getLineDash())

    // Baseline
    ctx.beginPath()
    ctx.moveTo(p1.x, p1.y)
    ctx.lineTo(p2.x, p2.y)
    ctx.stroke()

    // Parallel line
    ctx.beginPath()
    ctx.moveTo(p1.x + nx * offset, p1.y + ny * offset)
    ctx.lineTo(p2.x + nx * offset, p2.y + ny * offset)
    ctx.stroke()
    ctx.setLineDash([])

    // Fill between
    if (this.drawing.style.fillOpacity) {
      ctx.fillStyle = this.drawing.style.color
      ctx.globalAlpha = this.drawing.style.fillOpacity
      ctx.beginPath()
      ctx.moveTo(p1.x, p1.y)
      ctx.lineTo(p2.x, p2.y)
      ctx.lineTo(p2.x + nx * offset, p2.y + ny * offset)
      ctx.lineTo(p1.x + nx * offset, p1.y + ny * offset)
      ctx.closePath()
      ctx.fill()
      ctx.globalAlpha = 1
    }
  }
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/plugins/channel.ts
git commit -m "feat: add channel drawing plugin"
```

### Task 9: Rectangle Plugin

**Files:**
- Create: `src/lib/chart/plugins/rectangle.ts`

- [ ] **Step 1: Create rectangle plugin**

```typescript
// src/lib/chart/plugins/rectangle.ts
import { BaseDrawingPlugin } from './base-drawing'

export class RectanglePlugin extends BaseDrawingPlugin {
  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    if (this.drawing.points.length < 2) return
    const p1 = this.pointToPixel(this.drawing.points[0])
    const p2 = this.pointToPixel(this.drawing.points[1])
    if (!p1 || !p2) return

    const x = Math.min(p1.x, p2.x)
    const y = Math.min(p1.y, p2.y)
    const w = Math.abs(p2.x - p1.x)
    const h = Math.abs(p2.y - p1.y)

    // Fill
    if (this.drawing.style.fillOpacity) {
      ctx.fillStyle = this.drawing.style.color
      ctx.globalAlpha = this.drawing.style.fillOpacity
      ctx.fillRect(x, y, w, h)
      ctx.globalAlpha = 1
    }

    // Border
    ctx.strokeStyle = this.drawing.style.color
    ctx.lineWidth = this.drawing.style.lineWidth
    ctx.setLineDash(this.getLineDash())
    ctx.strokeRect(x, y, w, h)
    ctx.setLineDash([])
  }
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/plugins/rectangle.ts
git commit -m "feat: add rectangle drawing plugin"
```

### Task 10: Fibonacci Retracement Plugin

**Files:**
- Create: `src/lib/chart/plugins/fib-retracement.ts`

- [ ] **Step 1: Create fib retracement plugin**

```typescript
// src/lib/chart/plugins/fib-retracement.ts
import { BaseDrawingPlugin } from './base-drawing'

const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]

export class FibRetracementPlugin extends BaseDrawingPlugin {
  drawOnCanvas(ctx: CanvasRenderingContext2D, width: number, _height: number): void {
    if (this.drawing.points.length < 2) return
    const y1 = this.priceToY(this.drawing.points[0].price)
    const y2 = this.priceToY(this.drawing.points[1].price)
    if (y1 === null || y2 === null) return

    const highPrice = Math.max(this.drawing.points[0].price, this.drawing.points[1].price)
    const lowPrice = Math.min(this.drawing.points[0].price, this.drawing.points[1].price)
    const range = highPrice - lowPrice
    if (range === 0) return

    ctx.font = '10px -apple-system, system-ui, sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'

    for (const level of FIB_LEVELS) {
      const price = highPrice - range * level
      const y = this.priceToY(price)
      if (y === null) continue

      // Line
      ctx.beginPath()
      ctx.strokeStyle = this.drawing.style.color
      ctx.lineWidth = level === 0 || level === 1 ? this.drawing.style.lineWidth : 1
      ctx.setLineDash(level === 0.5 ? [4, 4] : this.getLineDash())
      ctx.moveTo(0, y)
      ctx.lineTo(width, y)
      ctx.stroke()
      ctx.setLineDash([])

      // Label
      ctx.fillStyle = this.drawing.style.color
      ctx.globalAlpha = 0.7
      ctx.fillText(`${(level * 100).toFixed(1)}% — ${price.toFixed(2)}`, 8, y - 8)
      ctx.globalAlpha = 1
    }

    // Fill zones between levels
    if (this.drawing.style.fillOpacity) {
      ctx.globalAlpha = this.drawing.style.fillOpacity * 0.5
      for (let i = 0; i < FIB_LEVELS.length - 1; i++) {
        const priceA = highPrice - range * FIB_LEVELS[i]
        const priceB = highPrice - range * FIB_LEVELS[i + 1]
        const yA = this.priceToY(priceA)
        const yB = this.priceToY(priceB)
        if (yA === null || yB === null) continue
        ctx.fillStyle = i % 2 === 0 ? this.drawing.style.color : `${this.drawing.style.color}66`
        ctx.fillRect(0, Math.min(yA, yB), width, Math.abs(yB - yA))
      }
      ctx.globalAlpha = 1
    }
  }
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/plugins/fib-retracement.ts
git commit -m "feat: add fibonacci retracement drawing plugin"
```

### Task 11: Measure / Price Range Plugin

**Files:**
- Create: `src/lib/chart/plugins/measure.ts`

- [ ] **Step 1: Create measure plugin**

```typescript
// src/lib/chart/plugins/measure.ts
import { BaseDrawingPlugin } from './base-drawing'

export class MeasurePlugin extends BaseDrawingPlugin {
  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    if (this.drawing.points.length < 2) return
    const p1 = this.pointToPixel(this.drawing.points[0])
    const p2 = this.pointToPixel(this.drawing.points[1])
    if (!p1 || !p2) return

    const priceDiff = this.drawing.points[1].price - this.drawing.points[0].price
    const pricePct = (priceDiff / this.drawing.points[0].price) * 100
    const isPositive = priceDiff >= 0

    const x = Math.min(p1.x, p2.x)
    const y = Math.min(p1.y, p2.y)
    const w = Math.abs(p2.x - p1.x)
    const h = Math.abs(p2.y - p1.y)

    // Shaded area
    ctx.fillStyle = isPositive ? 'rgba(76,175,80,0.1)' : 'rgba(229,57,53,0.1)'
    ctx.fillRect(x, y, w, h)

    // Border
    ctx.strokeStyle = isPositive ? '#4caf50' : '#e53935'
    ctx.lineWidth = 1
    ctx.setLineDash([4, 3])
    ctx.strokeRect(x, y, w, h)
    ctx.setLineDash([])

    // Label
    const sign = priceDiff >= 0 ? '+' : ''
    const label = `${sign}${priceDiff.toFixed(2)} (${sign}${pricePct.toFixed(2)}%)`
    ctx.font = 'bold 11px -apple-system, system-ui, sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = isPositive ? '#4caf50' : '#e53935'
    ctx.fillText(label, x + w / 2, y + h / 2)
  }
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/plugins/measure.ts
git commit -m "feat: add measure/price-range drawing plugin"
```

### Task 12: Plugin Registry

**Files:**
- Create: `src/lib/chart/plugins/index.ts`

- [ ] **Step 1: Create plugin factory**

```typescript
// src/lib/chart/plugins/index.ts
import type { Drawing } from '../types'
import type { BaseDrawingPlugin } from './base-drawing'
import { HorizontalLinePlugin } from './hline'
import { VerticalLinePlugin } from './vline'
import { TrendLinePlugin } from './trendline'
import { ChannelPlugin } from './channel'
import { RectanglePlugin } from './rectangle'
import { FibRetracementPlugin } from './fib-retracement'
import { MeasurePlugin } from './measure'

export function createDrawingPlugin(drawing: Drawing): BaseDrawingPlugin {
  switch (drawing.type) {
    case 'hline': return new HorizontalLinePlugin(drawing)
    case 'vline': return new VerticalLinePlugin(drawing)
    case 'trendline': return new TrendLinePlugin(drawing)
    case 'channel': return new ChannelPlugin(drawing)
    case 'rectangle': return new RectanglePlugin(drawing)
    case 'fib': return new FibRetracementPlugin(drawing)
    case 'measure': return new MeasurePlugin(drawing)
  }
}

export { BaseDrawingPlugin } from './base-drawing'
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/plugins/index.ts
git commit -m "feat: add drawing plugin registry/factory"
```

---

## Chunk 3: Drawing Manager & Toolbar UI

### Task 13: Drawing Manager

**Files:**
- Create: `src/lib/chart/drawing-manager.ts`

- [ ] **Step 1: Create DrawingManager class**

The manager handles attaching/detaching plugins to the chart series, and provides a method to sync drawings from the store.

```typescript
// src/lib/chart/drawing-manager.ts
import type { ISeriesApi } from 'lightweight-charts'
import type { Drawing } from './types'
import type { BaseDrawingPlugin } from './plugins'
import { createDrawingPlugin } from './plugins'

export class DrawingManager {
  private _series: ISeriesApi<'Candlestick'>
  private _plugins: Map<string, BaseDrawingPlugin> = new Map()

  constructor(series: ISeriesApi<'Candlestick'>) {
    this._series = series
  }

  /** Sync the plugin set to match the given drawings array */
  sync(drawings: Drawing[]): void {
    const drawingIds = new Set(drawings.map((d) => d.id))

    // Remove plugins for deleted drawings
    for (const [id, plugin] of this._plugins) {
      if (!drawingIds.has(id)) {
        this._series.detachPrimitive(plugin)
        this._plugins.delete(id)
      }
    }

    // Add or update plugins
    for (const drawing of drawings) {
      const existing = this._plugins.get(drawing.id)
      if (existing) {
        existing.updateDrawing(drawing)
      } else {
        const plugin = createDrawingPlugin(drawing)
        this._series.attachPrimitive(plugin)
        this._plugins.set(drawing.id, plugin)
      }
    }
  }

  /** Remove all plugins from the chart */
  destroy(): void {
    for (const [, plugin] of this._plugins) {
      this._series.detachPrimitive(plugin)
    }
    this._plugins.clear()
  }
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/drawing-manager.ts
git commit -m "feat: add DrawingManager class for plugin lifecycle"
```

### Task 14: Drawing Toolbar Component

**Files:**
- Create: `src/components/chart/DrawingToolbar.tsx`

- [ ] **Step 1: Create the toolbar component**

```typescript
// src/components/chart/DrawingToolbar.tsx
import { memo } from 'react'
import { Trash2 } from 'lucide-react'
import type { DrawingType } from '../../lib/chart/types'

interface Props {
  activeTool: DrawingType | null
  onSelectTool: (tool: DrawingType | null) => void
  onClearAll: () => void
  isCoarsePointer: boolean
}

const TOOLS: { type: DrawingType; label: string; icon: React.ReactNode }[] = [
  {
    type: 'hline',
    label: 'Horizontal Line',
    icon: (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <line x1="1" y1="7" x2="13" y2="7" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    type: 'vline',
    label: 'Vertical Line',
    icon: (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <line x1="7" y1="1" x2="7" y2="13" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    type: 'trendline',
    label: 'Trend Line',
    icon: (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <line x1="2" y1="12" x2="12" y2="2" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    type: 'channel',
    label: 'Channel',
    icon: (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <line x1="2" y1="10" x2="12" y2="4" stroke="currentColor" strokeWidth="1.5" />
        <line x1="2" y1="12" x2="12" y2="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 2" />
      </svg>
    ),
  },
  {
    type: 'rectangle',
    label: 'Rectangle',
    icon: (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <rect x="2" y="3" width="10" height="8" stroke="currentColor" strokeWidth="1.5" rx="1" />
      </svg>
    ),
  },
  {
    type: 'fib',
    label: 'Fib Retracement',
    icon: <span style={{ fontSize: 10, fontWeight: 700 }}>Fib</span>,
  },
  {
    type: 'measure',
    label: 'Measure',
    icon: (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <line x1="3" y1="3" x2="3" y2="11" stroke="currentColor" strokeWidth="1.5" />
        <line x1="11" y1="3" x2="11" y2="11" stroke="currentColor" strokeWidth="1.5" />
        <line x1="3" y1="7" x2="11" y2="7" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" />
      </svg>
    ),
  },
]

export const DrawingToolbar = memo(function DrawingToolbar({
  activeTool,
  onSelectTool,
  onClearAll,
  isCoarsePointer,
}: Props) {
  const size = isCoarsePointer ? 'w-[44px] h-[44px]' : 'w-[28px] h-[28px]'

  return (
    <div className="absolute left-0 top-0 z-20 flex h-full w-[36px] flex-col items-center gap-0.5 border-r border-[#2a2a2a] bg-[#1e1e1e]/95 py-1.5 backdrop-blur-sm md:w-[36px]">
      {TOOLS.map((tool) => (
        <button
          key={tool.type}
          onClick={() => onSelectTool(activeTool === tool.type ? null : tool.type)}
          className={`flex ${size} items-center justify-center rounded transition-colors ${
            activeTool === tool.type
              ? 'border border-brand/30 bg-brand/15 text-brand'
              : 'text-[#888] hover:bg-[#2a2a2a] hover:text-[#ccc]'
          }`}
          title={tool.label}
        >
          {tool.icon}
        </button>
      ))}
      <div className="flex-1" />
      <button
        onClick={onClearAll}
        className={`flex ${size} items-center justify-center rounded text-[#555] transition-colors hover:bg-[#2a2a2a] hover:text-[#e53935]`}
        title="Delete all drawings"
      >
        <Trash2 size={12} />
      </button>
    </div>
  )
})
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/components/chart/DrawingToolbar.tsx
git commit -m "feat: add DrawingToolbar component with 7 tool icons"
```

### Task 15: Wire Drawing System into NiftyChart

**Files:**
- Modify: `src/components/NiftyChart.tsx`

This is the integration task. It adds:
1. Draw button in the header bar (next to Vol)
2. Conditional DrawingToolbar render
3. DrawingManager instantiation in the chart creation effect
4. Drawing sync effect
5. Click handler for placing drawings

- [ ] **Step 1: Add imports at top of NiftyChart.tsx**

```typescript
import { Pencil } from 'lucide-react'
import { DrawingToolbar } from './chart/DrawingToolbar'
import { DrawingManager } from '../lib/chart/drawing-manager'
import { DEFAULT_DRAWING_STYLE } from '../lib/chart/types'
import type { DrawingType } from '../lib/chart/types'
```

- [ ] **Step 2: Add store bindings in the component**

In the `useStore(useShallow(...))` call (around line 220), add:

```typescript
drawingToolbar: state.drawingToolbar,
activeTool: state.activeTool,
drawings: state.drawings,
selectedDrawingId: state.selectedDrawingId,
drawingInProgress: state.drawingInProgress,
setDrawingToolbar: state.setDrawingToolbar,
setActiveTool: state.setActiveTool,
addDrawing: state.addDrawing,
loadDrawingsForSymbol: state.loadDrawingsForSymbol,
clearDrawings: state.clearDrawings,
```

- [ ] **Step 3: Add DrawingManager ref and sync effect**

After the existing refs (around line 268):

```typescript
const drawingManagerRef = useRef<DrawingManager | null>(null)
```

In the chart creation effect (around line 628, after `addCandlestickSeries`), instantiate:

```typescript
drawingManagerRef.current = new DrawingManager(series)
```

In the cleanup return, add before `chart.remove()`:

```typescript
drawingManagerRef.current?.destroy()
drawingManagerRef.current = null
```

Add a new effect to sync drawings to the manager:

```typescript
useEffect(() => {
  const symbol = chartQuote?.symbol ?? 'NIFTY 50'
  loadDrawingsForSymbol(symbol)
}, [chartQuote?.symbol, loadDrawingsForSymbol])

useEffect(() => {
  const symbol = chartQuote?.symbol ?? 'NIFTY 50'
  const symbolDrawings = drawings[symbol] ?? []
  drawingManagerRef.current?.sync(symbolDrawings)
}, [drawings, chartQuote?.symbol])
```

- [ ] **Step 4: Add Draw button in the header bar**

After the Vol button and its divider (around line 1078), add:

```typescript
<button
  onClick={() => setDrawingToolbar(!drawingToolbar)}
  className={`flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[11px] transition-colors ${
    drawingToolbar
      ? 'border-brand/60 bg-brand/10 text-text-primary'
      : 'border-border-primary text-text-muted hover:text-text-primary'
  }`}
  title={drawingToolbar ? 'Hide drawing tools' : 'Show drawing tools'}
>
  <Pencil size={10} />
  <span className="hidden md:inline">Draw</span>
</button>
<div className="mx-1 h-3 w-px bg-border-primary opacity-50" />
```

- [ ] **Step 5: Render DrawingToolbar in the chart container**

Inside the chart container div (around line 1139, the `ref={containerRef}` div), add at the top of its children:

```typescript
{drawingToolbar && (
  <DrawingToolbar
    activeTool={activeTool}
    onSelectTool={setActiveTool}
    onClearAll={() => clearDrawings(chartQuote?.symbol ?? 'NIFTY 50')}
    isCoarsePointer={isCoarsePointer}
  />
)}
```

- [ ] **Step 6: Add click-to-place drawing handler**

In the chart's click subscription (or add one), when `activeTool` is set, create a drawing at the clicked price-time coordinate. This wires into the existing chart click handler. Add a `useEffectEvent`:

```typescript
const handleDrawingClick = useEffectEvent((param: MouseEventParams) => {
  if (!activeTool || !param.time || !param.point) return
  const series = seriesRef.current
  if (!series) return

  const price = series.coordinateToPrice(param.point.y)
  if (price === null) return
  const time = Number(param.time)
  const symbol = chartQuote?.symbol ?? 'NIFTY 50'
  const point = { time, price: Number(price.toFixed(2)) }

  // Single-point tools
  if (activeTool === 'hline' || activeTool === 'vline') {
    addDrawing(symbol, {
      id: crypto.randomUUID(),
      type: activeTool,
      points: [point],
      style: { ...DEFAULT_DRAWING_STYLE },
      createdAt: Date.now(),
    })
    return
  }

  // Multi-point tools: accumulate points
  const current = drawingInProgress ?? []
  const next = [...current, point]

  const requiredPoints = activeTool === 'channel' ? 3 : 2
  if (next.length >= requiredPoints) {
    addDrawing(symbol, {
      id: crypto.randomUUID(),
      type: activeTool,
      points: next,
      style: { ...DEFAULT_DRAWING_STYLE },
      createdAt: Date.now(),
    })
    setDrawingInProgress(null)
  } else {
    setDrawingInProgress(next)
  }
})
```

Wire this into the chart's click subscription in the chart creation effect:

```typescript
chart.subscribeClick((param) => {
  handleDrawingClick(param)
})
```

- [ ] **Step 7: Add tool hint overlay**

Inside the chart container, show a hint when a tool is active:

```typescript
{activeTool && (
  <div className="pointer-events-none absolute left-10 top-2 z-30 rounded bg-[#1e1e1e]/80 px-2 py-1 text-[10px] text-text-muted backdrop-blur-sm">
    {activeTool === 'hline' ? 'Click to place horizontal line' :
     activeTool === 'vline' ? 'Click to place vertical line' :
     activeTool === 'channel' && drawingInProgress?.length === 2 ? 'Click to set channel width' :
     drawingInProgress?.length === 1 ? 'Click second point' :
     'Click first point'}
  </div>
)}
```

- [ ] **Step 8: Verify compile**

Run: `npx tsc --noEmit`

- [ ] **Step 9: Visual verification**

Run dev server (`npm run dev`), open browser. Verify:
- Draw button appears in header next to Vol
- Clicking Draw shows/hides the toolbar
- Clicking horizontal line tool → clicking chart places a line
- Line persists across timeframe changes (same symbol)
- Switching to option chart → different drawing set

- [ ] **Step 10: Commit**

```bash
git add src/components/NiftyChart.tsx
git commit -m "feat: integrate drawing system into chart — toolbar, manager, click-to-place"
```

---

## Chunk 4: Indicator Computation Functions

### Task 16: EMA & SMA

**Files:**
- Create: `src/lib/chart/indicators/ema.ts`
- Create: `src/lib/chart/indicators/sma.ts`

- [ ] **Step 1: Create EMA computation**

```typescript
// src/lib/chart/indicators/ema.ts
import type { Candle } from '../../api'

export function computeEMA(candles: Candle[], period: number): { time: number; value: number }[] {
  if (candles.length < period) return []
  const k = 2 / (period + 1)
  const result: { time: number; value: number }[] = []

  // SMA for initial value
  let sum = 0
  for (let i = 0; i < period; i++) sum += candles[i].close
  let ema = sum / period
  result.push({ time: candles[period - 1].time, value: ema })

  for (let i = period; i < candles.length; i++) {
    ema = candles[i].close * k + ema * (1 - k)
    result.push({ time: candles[i].time, value: ema })
  }
  return result
}
```

- [ ] **Step 2: Create SMA computation**

```typescript
// src/lib/chart/indicators/sma.ts
import type { Candle } from '../../api'

export function computeSMA(candles: Candle[], period: number): { time: number; value: number }[] {
  if (candles.length < period) return []
  const result: { time: number; value: number }[] = []
  let sum = 0
  for (let i = 0; i < period; i++) sum += candles[i].close
  result.push({ time: candles[period - 1].time, value: sum / period })

  for (let i = period; i < candles.length; i++) {
    sum += candles[i].close - candles[i - period].close
    result.push({ time: candles[i].time, value: sum / period })
  }
  return result
}
```

- [ ] **Step 3: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/indicators/ema.ts src/lib/chart/indicators/sma.ts
git commit -m "feat: add EMA and SMA computation functions"
```

### Task 17: Bollinger Bands

**Files:**
- Create: `src/lib/chart/indicators/bollinger.ts`

- [ ] **Step 1: Create Bollinger Bands computation**

```typescript
// src/lib/chart/indicators/bollinger.ts
import type { Candle } from '../../api'

type BollingerPoint = { time: number; middle: number; upper: number; lower: number }

export function computeBollinger(candles: Candle[], period: number, stdDev: number): BollingerPoint[] {
  if (candles.length < period) return []
  const result: BollingerPoint[] = []

  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) sum += candles[j].close
    const mean = sum / period

    let sqSum = 0
    for (let j = i - period + 1; j <= i; j++) sqSum += (candles[j].close - mean) ** 2
    const sd = Math.sqrt(sqSum / period)

    result.push({
      time: candles[i].time,
      middle: mean,
      upper: mean + stdDev * sd,
      lower: mean - stdDev * sd,
    })
  }
  return result
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/indicators/bollinger.ts
git commit -m "feat: add Bollinger Bands computation"
```

### Task 18: VWAP

**Files:**
- Create: `src/lib/chart/indicators/vwap.ts`

- [ ] **Step 1: Create VWAP computation**

VWAP resets each day. For intraday, it accumulates (typical_price * volume) / cumulative_volume. For daily+ timeframes, VWAP equals the typical price of each candle.

```typescript
// src/lib/chart/indicators/vwap.ts
import type { Candle } from '../../api'

export function computeVWAP(candles: Candle[]): { time: number; value: number }[] {
  if (candles.length === 0) return []
  const result: { time: number; value: number }[] = []
  let cumVol = 0
  let cumTPV = 0
  let lastDay = -1

  for (const candle of candles) {
    // Reset on new day (86400 seconds per day)
    const day = Math.floor(candle.time / 86400)
    if (day !== lastDay) {
      cumVol = 0
      cumTPV = 0
      lastDay = day
    }

    const tp = (candle.high + candle.low + candle.close) / 3
    cumVol += candle.volume
    cumTPV += tp * candle.volume

    if (cumVol > 0) {
      result.push({ time: candle.time, value: cumTPV / cumVol })
    }
  }
  return result
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/indicators/vwap.ts
git commit -m "feat: add VWAP computation"
```

### Task 19: Supertrend

**Files:**
- Create: `src/lib/chart/indicators/supertrend.ts`

- [ ] **Step 1: Create Supertrend computation**

```typescript
// src/lib/chart/indicators/supertrend.ts
import type { Candle } from '../../api'

type SupertrendPoint = { time: number; value: number; direction: 'up' | 'down' }

export function computeSupertrend(candles: Candle[], period: number, multiplier: number): SupertrendPoint[] {
  if (candles.length < period) return []

  // ATR computation
  const tr: number[] = []
  for (let i = 0; i < candles.length; i++) {
    if (i === 0) {
      tr.push(candles[i].high - candles[i].low)
    } else {
      tr.push(Math.max(
        candles[i].high - candles[i].low,
        Math.abs(candles[i].high - candles[i - 1].close),
        Math.abs(candles[i].low - candles[i - 1].close),
      ))
    }
  }

  const result: SupertrendPoint[] = []
  let atr = 0
  for (let i = 0; i < period; i++) atr += tr[i]
  atr /= period

  let upperBand = 0
  let lowerBand = 0
  let supertrend = 0
  let direction: 'up' | 'down' = 'up'

  for (let i = period; i < candles.length; i++) {
    // Update ATR (RMA)
    atr = (atr * (period - 1) + tr[i]) / period

    const hl2 = (candles[i].high + candles[i].low) / 2
    const newUpper = hl2 + multiplier * atr
    const newLower = hl2 - multiplier * atr

    upperBand = newUpper < upperBand || candles[i - 1].close > upperBand ? newUpper : upperBand
    lowerBand = newLower > lowerBand || candles[i - 1].close < lowerBand ? newLower : lowerBand

    if (supertrend === upperBand) {
      direction = candles[i].close > upperBand ? 'up' : 'down'
    } else {
      direction = candles[i].close < lowerBand ? 'down' : 'up'
    }

    supertrend = direction === 'up' ? lowerBand : upperBand
    result.push({ time: candles[i].time, value: supertrend, direction })
  }
  return result
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/indicators/supertrend.ts
git commit -m "feat: add Supertrend computation"
```

### Task 20: Ichimoku

**Files:**
- Create: `src/lib/chart/indicators/ichimoku.ts`

- [ ] **Step 1: Create Ichimoku computation**

```typescript
// src/lib/chart/indicators/ichimoku.ts
import type { Candle } from '../../api'

type IchimokuPoint = {
  time: number
  tenkan: number | null
  kijun: number | null
  senkouA: number | null
  senkouB: number | null
  chikou: number | null
}

function highLow(candles: Candle[], end: number, period: number): { high: number; low: number } | null {
  const start = end - period + 1
  if (start < 0) return null
  let high = -Infinity
  let low = Infinity
  for (let i = start; i <= end; i++) {
    if (candles[i].high > high) high = candles[i].high
    if (candles[i].low < low) low = candles[i].low
  }
  return { high, low }
}

export function computeIchimoku(
  candles: Candle[],
  tenkanPeriod: number,
  kijunPeriod: number,
  senkouPeriod: number,
): IchimokuPoint[] {
  const result: IchimokuPoint[] = []

  for (let i = 0; i < candles.length; i++) {
    const tenkanHL = highLow(candles, i, tenkanPeriod)
    const kijunHL = highLow(candles, i, kijunPeriod)
    const senkouBHL = highLow(candles, i, senkouPeriod)

    const tenkan = tenkanHL ? (tenkanHL.high + tenkanHL.low) / 2 : null
    const kijun = kijunHL ? (kijunHL.high + kijunHL.low) / 2 : null
    const senkouA = tenkan !== null && kijun !== null ? (tenkan + kijun) / 2 : null
    const senkouB = senkouBHL ? (senkouBHL.high + senkouBHL.low) / 2 : null
    const chikou = candles[i].close  // plotted 26 periods back

    result.push({ time: candles[i].time, tenkan, kijun, senkouA, senkouB, chikou })
  }
  return result
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/indicators/ichimoku.ts
git commit -m "feat: add Ichimoku computation"
```

### Task 21: RSI

**Files:**
- Create: `src/lib/chart/indicators/rsi.ts`

- [ ] **Step 1: Create RSI computation**

```typescript
// src/lib/chart/indicators/rsi.ts
import type { Candle } from '../../api'

export function computeRSI(candles: Candle[], period: number): { time: number; value: number }[] {
  if (candles.length < period + 1) return []
  const result: { time: number; value: number }[] = []

  let avgGain = 0
  let avgLoss = 0
  for (let i = 1; i <= period; i++) {
    const diff = candles[i].close - candles[i - 1].close
    if (diff > 0) avgGain += diff
    else avgLoss -= diff
  }
  avgGain /= period
  avgLoss /= period

  const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
  result.push({ time: candles[period].time, value: 100 - 100 / (1 + rs) })

  for (let i = period + 1; i < candles.length; i++) {
    const diff = candles[i].close - candles[i - 1].close
    const gain = diff > 0 ? diff : 0
    const loss = diff < 0 ? -diff : 0
    avgGain = (avgGain * (period - 1) + gain) / period
    avgLoss = (avgLoss * (period - 1) + loss) / period
    const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
    result.push({ time: candles[i].time, value: rsi })
  }
  return result
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/indicators/rsi.ts
git commit -m "feat: add RSI computation"
```

### Task 22: MACD

**Files:**
- Create: `src/lib/chart/indicators/macd.ts`

- [ ] **Step 1: Create MACD computation**

```typescript
// src/lib/chart/indicators/macd.ts
import type { Candle } from '../../api'

type MACDPoint = { time: number; macd: number; signal: number; histogram: number }

export function computeMACD(
  candles: Candle[],
  fastPeriod: number,
  slowPeriod: number,
  signalPeriod: number,
): MACDPoint[] {
  if (candles.length < slowPeriod + signalPeriod) return []

  const kFast = 2 / (fastPeriod + 1)
  const kSlow = 2 / (slowPeriod + 1)
  const kSignal = 2 / (signalPeriod + 1)

  // Initialize EMAs
  let fastEma = 0
  let slowEma = 0
  for (let i = 0; i < slowPeriod; i++) {
    if (i < fastPeriod) fastEma += candles[i].close
    slowEma += candles[i].close
  }
  fastEma = fastEma / fastPeriod
  slowEma = slowEma / slowPeriod

  // Compute fast/slow from fastPeriod onward, MACD from slowPeriod onward
  for (let i = fastPeriod; i < slowPeriod; i++) {
    fastEma = candles[i].close * kFast + fastEma * (1 - kFast)
  }

  const macdValues: { time: number; macd: number }[] = []
  for (let i = slowPeriod; i < candles.length; i++) {
    fastEma = candles[i].close * kFast + fastEma * (1 - kFast)
    slowEma = candles[i].close * kSlow + slowEma * (1 - kSlow)
    macdValues.push({ time: candles[i].time, macd: fastEma - slowEma })
  }

  if (macdValues.length < signalPeriod) return []

  // Signal line
  let signalEma = 0
  for (let i = 0; i < signalPeriod; i++) signalEma += macdValues[i].macd
  signalEma /= signalPeriod

  const result: MACDPoint[] = []
  for (let i = signalPeriod - 1; i < macdValues.length; i++) {
    if (i >= signalPeriod) {
      signalEma = macdValues[i].macd * kSignal + signalEma * (1 - kSignal)
    }
    result.push({
      time: macdValues[i].time,
      macd: macdValues[i].macd,
      signal: signalEma,
      histogram: macdValues[i].macd - signalEma,
    })
  }
  return result
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/indicators/macd.ts
git commit -m "feat: add MACD computation"
```

### Task 23: ADX

**Files:**
- Create: `src/lib/chart/indicators/adx.ts`

- [ ] **Step 1: Create ADX computation**

```typescript
// src/lib/chart/indicators/adx.ts
import type { Candle } from '../../api'

type ADXPoint = { time: number; adx: number; plusDI: number; minusDI: number }

export function computeADX(candles: Candle[], period: number): ADXPoint[] {
  if (candles.length < period * 2 + 1) return []

  const tr: number[] = []
  const plusDM: number[] = []
  const minusDM: number[] = []

  for (let i = 1; i < candles.length; i++) {
    const highDiff = candles[i].high - candles[i - 1].high
    const lowDiff = candles[i - 1].low - candles[i].low

    tr.push(Math.max(
      candles[i].high - candles[i].low,
      Math.abs(candles[i].high - candles[i - 1].close),
      Math.abs(candles[i].low - candles[i - 1].close),
    ))
    plusDM.push(highDiff > lowDiff && highDiff > 0 ? highDiff : 0)
    minusDM.push(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0)
  }

  // Smooth with Wilder's method
  let smoothTR = 0
  let smoothPlusDM = 0
  let smoothMinusDM = 0
  for (let i = 0; i < period; i++) {
    smoothTR += tr[i]
    smoothPlusDM += plusDM[i]
    smoothMinusDM += minusDM[i]
  }

  const dxValues: number[] = []
  const result: ADXPoint[] = []

  for (let i = period; i < tr.length; i++) {
    smoothTR = smoothTR - smoothTR / period + tr[i]
    smoothPlusDM = smoothPlusDM - smoothPlusDM / period + plusDM[i]
    smoothMinusDM = smoothMinusDM - smoothMinusDM / period + minusDM[i]

    const pdi = smoothTR === 0 ? 0 : (smoothPlusDM / smoothTR) * 100
    const mdi = smoothTR === 0 ? 0 : (smoothMinusDM / smoothTR) * 100
    const dx = pdi + mdi === 0 ? 0 : (Math.abs(pdi - mdi) / (pdi + mdi)) * 100
    dxValues.push(dx)

    if (dxValues.length >= period) {
      let adx: number
      if (dxValues.length === period) {
        adx = 0
        for (let j = 0; j < period; j++) adx += dxValues[j]
        adx /= period
      } else {
        const prevAdx = result[result.length - 1].adx
        adx = (prevAdx * (period - 1) + dx) / period
      }
      result.push({ time: candles[i + 1].time, adx, plusDI: pdi, minusDI: mdi })
    }
  }
  return result
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/indicators/adx.ts
git commit -m "feat: add ADX computation"
```

### Task 24: Indicator Index

**Files:**
- Create: `src/lib/chart/indicators/index.ts`

- [ ] **Step 1: Create barrel export**

```typescript
// src/lib/chart/indicators/index.ts
export { computeEMA } from './ema'
export { computeSMA } from './sma'
export { computeBollinger } from './bollinger'
export { computeVWAP } from './vwap'
export { computeSupertrend } from './supertrend'
export { computeIchimoku } from './ichimoku'
export { computeRSI } from './rsi'
export { computeMACD } from './macd'
export { computeADX } from './adx'
```

- [ ] **Step 2: Commit**

```bash
git add src/lib/chart/indicators/index.ts
git commit -m "feat: add indicator computation barrel export"
```

---

## Chunk 5: Indicator Manager & Overlay Rendering

### Task 25: Indicator Manager

**Files:**
- Create: `src/lib/chart/indicator-manager.ts`

- [ ] **Step 1: Create IndicatorManager class**

This class manages line series for overlay indicators on the main chart. It takes raw candles, computes indicator values, and renders them as LineSeries. It also applies the IST offset to computed timestamps.

```typescript
// src/lib/chart/indicator-manager.ts
import type { IChartApi, ISeriesApi, Time } from 'lightweight-charts'
import type { Candle } from '../api'
import type { IndicatorConfig } from './types'
import { OVERLAY_INDICATORS } from './types'
import { computeEMA, computeSMA, computeBollinger, computeVWAP, computeSupertrend, computeIchimoku } from './indicators'

const IST_OFFSET_SECONDS = 5.5 * 60 * 60

export class IndicatorManager {
  private _chart: IChartApi
  private _seriesMap: Map<string, ISeriesApi<'Line'>[]> = new Map()

  constructor(chart: IChartApi) {
    this._chart = chart
  }

  /** Recompute and render all enabled overlay indicators */
  update(configs: IndicatorConfig[], candles: Candle[]): void {
    // Remove series for disabled indicators
    for (const [id, seriesList] of this._seriesMap) {
      const config = configs.find((c) => c.id === id)
      if (!config || !config.enabled || !OVERLAY_INDICATORS.includes(config.type)) {
        for (const s of seriesList) this._chart.removeSeries(s)
        this._seriesMap.delete(id)
      }
    }

    // Add/update enabled overlay indicators
    for (const config of configs) {
      if (!config.enabled || !OVERLAY_INDICATORS.includes(config.type)) continue
      this._renderOverlay(config, candles)
    }
  }

  private _renderOverlay(config: IndicatorConfig, candles: Candle[]): void {
    switch (config.type) {
      case 'ema': return this._renderLine(config, computeEMA(candles, config.params.period))
      case 'sma': return this._renderLine(config, computeSMA(candles, config.params.period))
      case 'vwap': return this._renderLine(config, computeVWAP(candles))
      case 'bb': return this._renderBollinger(config, candles)
      case 'supertrend': return this._renderSupertrend(config, candles)
      case 'ichimoku': return this._renderIchimoku(config, candles)
    }
  }

  private _renderLine(config: IndicatorConfig, data: { time: number; value: number }[]): void {
    const seriesData = data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.value }))
    let seriesList = this._seriesMap.get(config.id)
    if (!seriesList) {
      const series = this._chart.addLineSeries({
        color: config.color,
        lineWidth: config.lineWidth,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      seriesList = [series]
      this._seriesMap.set(config.id, seriesList)
    }
    seriesList[0].setData(seriesData)
  }

  private _renderBollinger(config: IndicatorConfig, candles: Candle[]): void {
    const data = computeBollinger(candles, config.params.period, config.params.stdDev)
    let seriesList = this._seriesMap.get(config.id)
    if (!seriesList) {
      const upper = this._chart.addLineSeries({ color: config.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const middle = this._chart.addLineSeries({ color: config.color, lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const lower = this._chart.addLineSeries({ color: config.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      seriesList = [upper, middle, lower]
      this._seriesMap.set(config.id, seriesList)
    }
    seriesList[0].setData(data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.upper })))
    seriesList[1].setData(data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.middle })))
    seriesList[2].setData(data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.lower })))
  }

  private _renderSupertrend(config: IndicatorConfig, candles: Candle[]): void {
    const data = computeSupertrend(candles, config.params.period, config.params.multiplier)
    let seriesList = this._seriesMap.get(config.id)
    if (!seriesList) {
      const bullLine = this._chart.addLineSeries({ color: '#4caf50', lineWidth: config.lineWidth, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const bearLine = this._chart.addLineSeries({ color: '#e53935', lineWidth: config.lineWidth, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      seriesList = [bullLine, bearLine]
      this._seriesMap.set(config.id, seriesList)
    }
    // Split into bull/bear segments with gaps
    const bull = data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.direction === 'up' ? d.value : NaN }))
    const bear = data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.direction === 'down' ? d.value : NaN }))
    seriesList[0].setData(bull)
    seriesList[1].setData(bear)
  }

  private _renderIchimoku(config: IndicatorConfig, candles: Candle[]): void {
    const data = computeIchimoku(candles, config.params.tenkan, config.params.kijun, config.params.senkou)
    let seriesList = this._seriesMap.get(config.id)
    if (!seriesList) {
      const tenkan = this._chart.addLineSeries({ color: '#0ea5e9', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const kijun = this._chart.addLineSeries({ color: '#e53935', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const senkouA = this._chart.addLineSeries({ color: '#4caf50', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const senkouB = this._chart.addLineSeries({ color: '#e53935', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const chikou = this._chart.addLineSeries({ color: '#8b5cf6', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      seriesList = [tenkan, kijun, senkouA, senkouB, chikou]
      this._seriesMap.set(config.id, seriesList)
    }

    const shift = config.params.kijun  // Senkou lines are shifted 26 periods forward
    seriesList[0].setData(data.filter((d) => d.tenkan !== null).map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.tenkan! })))
    seriesList[1].setData(data.filter((d) => d.kijun !== null).map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.kijun! })))
    // Senkou lines shifted forward by kijun periods — approximate by skipping
    seriesList[2].setData(data.filter((d) => d.senkouA !== null).map((d, _i, arr) => {
      const shifted = arr[Math.min(arr.indexOf(d) + shift, arr.length - 1)]
      return { time: (shifted.time + IST_OFFSET_SECONDS) as Time, value: d.senkouA! }
    }))
    seriesList[3].setData(data.filter((d) => d.senkouB !== null).map((d, _i, arr) => {
      const shifted = arr[Math.min(arr.indexOf(d) + shift, arr.length - 1)]
      return { time: (shifted.time + IST_OFFSET_SECONDS) as Time, value: d.senkouB! }
    }))
    // Chikou shifted back by kijun periods
    seriesList[4].setData(data.slice(shift).map((d, i) => ({ time: (data[i].time + IST_OFFSET_SECONDS) as Time, value: d.chikou! })))
  }

  /** Remove all indicator series from chart */
  destroy(): void {
    for (const [, seriesList] of this._seriesMap) {
      for (const s of seriesList) this._chart.removeSeries(s)
    }
    this._seriesMap.clear()
  }
}
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/lib/chart/indicator-manager.ts
git commit -m "feat: add IndicatorManager for overlay indicator rendering"
```

---

## Chunk 6: Indicator UI Components

### Task 26: Indicator Panel Dropdown

**Files:**
- Create: `src/components/chart/IndicatorPanel.tsx`

- [ ] **Step 1: Create the dropdown component**

```typescript
// src/components/chart/IndicatorPanel.tsx
import { memo, useEffect, useRef } from 'react'
import type { IndicatorConfig, IndicatorType } from '../../lib/chart/types'
import { OVERLAY_INDICATORS, OSCILLATOR_INDICATORS } from '../../lib/chart/types'

interface Props {
  indicators: IndicatorConfig[]
  onToggle: (id: string) => void
  onClose: () => void
}

const LABELS: Record<IndicatorType, string> = {
  ema: 'EMA',
  sma: 'SMA',
  bb: 'Bollinger',
  vwap: 'VWAP',
  supertrend: 'Supertrend',
  ichimoku: 'Ichimoku',
  rsi: 'RSI',
  macd: 'MACD',
  adx: 'ADX',
}

export const IndicatorPanel = memo(function IndicatorPanel({ indicators, onToggle, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  const overlays = indicators.filter((i) => OVERLAY_INDICATORS.includes(i.type))
  const oscillators = indicators.filter((i) => OSCILLATOR_INDICATORS.includes(i.type))

  return (
    <div
      ref={ref}
      className="absolute right-2 top-[34px] z-30 w-[260px] rounded-lg border border-[#3a3a3a] bg-[#222] shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
    >
      <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-[#666]">
        Overlay
      </div>
      <div className="flex flex-wrap gap-1 px-2 pb-2">
        {overlays.map((ind) => (
          <button
            key={ind.id}
            onClick={() => onToggle(ind.id)}
            className={`rounded px-2.5 py-1 text-[11px] transition-colors ${
              ind.enabled
                ? 'border border-brand/30 bg-brand/15 text-brand'
                : 'border border-[#3a3a3a] bg-[#2a2a2a] text-[#999] hover:border-[#555] hover:text-[#ccc]'
            }`}
          >
            {LABELS[ind.type]}{ind.enabled ? ' ✓' : ''}
          </button>
        ))}
      </div>
      <div className="mx-2 border-t border-[#333]" />
      <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-[#666]">
        Oscillator
      </div>
      <div className="flex flex-wrap gap-1 px-2 pb-2">
        {oscillators.map((ind) => (
          <button
            key={ind.id}
            onClick={() => onToggle(ind.id)}
            className={`rounded px-2.5 py-1 text-[11px] transition-colors ${
              ind.enabled
                ? 'border border-brand/30 bg-brand/15 text-brand'
                : 'border border-[#3a3a3a] bg-[#2a2a2a] text-[#999] hover:border-[#555] hover:text-[#ccc]'
            }`}
          >
            {LABELS[ind.type]}{ind.enabled ? ' ✓' : ''}
          </button>
        ))}
      </div>
    </div>
  )
})
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/components/chart/IndicatorPanel.tsx
git commit -m "feat: add IndicatorPanel dropdown component"
```

### Task 27: Oscillator Pane Component

**Files:**
- Create: `src/components/chart/OscillatorPane.tsx`

- [ ] **Step 1: Create the collapsible oscillator sub-chart**

```typescript
// src/components/chart/OscillatorPane.tsx
import { memo, useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { createChart } from 'lightweight-charts'
import type { IChartApi, ISeriesApi, LogicalRange, Time } from 'lightweight-charts'
import type { IndicatorConfig } from '../../lib/chart/types'

interface Props {
  config: IndicatorConfig
  data: { time: number; value: number }[]
  /** Additional data lines (e.g. MACD signal, ADX +DI/-DI) */
  extraLines?: { data: { time: number; value: number }[]; color: string }[]
  /** Histogram data for MACD */
  histogram?: { time: number; value: number }[]
  /** Reference lines (e.g. 30/70 for RSI) */
  referenceLines?: number[]
  expanded: boolean
  currentValue: number | null
  visibleRange: LogicalRange | null
  onToggleExpanded: () => void
  onRemove: () => void
}

const LABELS: Record<string, string> = {
  rsi: 'RSI',
  macd: 'MACD',
  adx: 'ADX',
}

const IST_OFFSET_SECONDS = 5.5 * 60 * 60

export const OscillatorPane = memo(function OscillatorPane({
  config,
  data,
  extraLines,
  histogram,
  referenceLines,
  expanded,
  currentValue,
  visibleRange,
  onToggleExpanded,
  onRemove,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const mainSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const isSyncingRef = useRef(false)

  // Create / destroy chart
  useEffect(() => {
    if (!expanded || !containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 80,
      layout: { background: { color: '#1a1a1a' }, textColor: '#555', fontSize: 9 },
      grid: { vertLines: { visible: false }, horzLines: { color: '#222' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { visible: false, borderVisible: false },
      crosshair: { mode: 0 },
      handleScroll: false,
      handleScale: false,
    })

    const mainSeries = chart.addLineSeries({
      color: config.color,
      lineWidth: config.lineWidth,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
    })

    mainSeries.setData(data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.value })))

    // Extra lines (signal, +DI, -DI)
    if (extraLines) {
      for (const line of extraLines) {
        const s = chart.addLineSeries({
          color: line.color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        })
        s.setData(line.data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.value })))
      }
    }

    // Histogram (MACD)
    if (histogram) {
      const h = chart.addHistogramSeries({
        priceLineVisible: false,
        lastValueVisible: false,
        priceScaleId: '',
      })
      h.setData(histogram.map((d) => ({
        time: (d.time + IST_OFFSET_SECONDS) as Time,
        value: d.value,
        color: d.value >= 0 ? 'rgba(76,175,80,0.5)' : 'rgba(229,57,53,0.5)',
      })))
    }

    chartRef.current = chart
    mainSeriesRef.current = mainSeries

    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width
      if (w > 0) chart.applyOptions({ width: w })
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      mainSeriesRef.current = null
    }
  }, [expanded, config.color, config.lineWidth]) // eslint-disable-line react-hooks/exhaustive-deps

  // Sync visible range from main chart
  useEffect(() => {
    if (!chartRef.current || !visibleRange || isSyncingRef.current) return
    isSyncingRef.current = true
    chartRef.current.timeScale().setVisibleLogicalRange(visibleRange)
    requestAnimationFrame(() => { isSyncingRef.current = false })
  }, [visibleRange])

  const paramStr = Object.values(config.params).join(', ')

  return (
    <div className="border-t border-[#2a2a2a]">
      <div
        className="flex cursor-pointer items-center px-2 py-0.5"
        style={{ height: 22, background: '#1e1e1e' }}
        onClick={onToggleExpanded}
      >
        <span className="mr-1 text-[10px] text-[#888]">{expanded ? '▼' : '▶'}</span>
        <span className="text-[10px] font-medium text-[#999]">{LABELS[config.type] ?? config.type}</span>
        <span className="ml-1 text-[10px] text-[#666]">({paramStr})</span>
        <span className="ml-auto tabular-nums text-[10px] font-semibold text-brand">
          {currentValue !== null ? currentValue.toFixed(1) : '—'}
        </span>
        <button
          onClick={(e) => { e.stopPropagation(); onRemove() }}
          className="ml-2 text-[#555] transition-colors hover:text-[#e53935]"
        >
          <X size={10} />
        </button>
      </div>
      {expanded && (
        <div ref={containerRef} style={{ height: 80 }} />
      )}
    </div>
  )
})
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/components/chart/OscillatorPane.tsx
git commit -m "feat: add OscillatorPane collapsible sub-chart component"
```

### Task 28: Wire Indicators into NiftyChart

**Files:**
- Modify: `src/components/NiftyChart.tsx`

- [ ] **Step 1: Add imports**

```typescript
import { BarChart2 } from 'lucide-react'
import { IndicatorPanel } from './chart/IndicatorPanel'
import { OscillatorPane } from './chart/OscillatorPane'
import { IndicatorManager } from '../lib/chart/indicator-manager'
import { OSCILLATOR_INDICATORS } from '../lib/chart/types'
import { computeRSI, computeMACD, computeADX } from '../lib/chart/indicators'
```

- [ ] **Step 2: Add store bindings**

In the `useShallow` selector, add:

```typescript
indicatorPanelOpen: state.indicatorPanelOpen,
indicators: state.indicators,
oscillatorPaneState: state.oscillatorPaneState,
setIndicatorPanelOpen: state.setIndicatorPanelOpen,
toggleIndicator: state.toggleIndicator,
setOscillatorPaneExpanded: state.setOscillatorPaneExpanded,
```

- [ ] **Step 3: Add IndicatorManager ref and lifecycle**

```typescript
const indicatorManagerRef = useRef<IndicatorManager | null>(null)
const [visibleLogicalRange, setVisibleLogicalRange] = useState<LogicalRange | null>(null)
```

In chart creation effect, after `createChart()`:

```typescript
indicatorManagerRef.current = new IndicatorManager(chart)
```

In cleanup:

```typescript
indicatorManagerRef.current?.destroy()
indicatorManagerRef.current = null
```

- [ ] **Step 4: Add indicator update effect**

After candle data loads / updates:

```typescript
useEffect(() => {
  if (!indicatorManagerRef.current) return
  const overlayConfigs = indicators.filter((i) => i.enabled && !OSCILLATOR_INDICATORS.includes(i.type))
  if (overlayConfigs.length === 0 && !indicators.some((i) => i.enabled)) {
    indicatorManagerRef.current.update([], [])
    return
  }
  indicatorManagerRef.current.update(indicators, rawCandlesRef.current)
}, [indicators, /* trigger on candle data change via a revision counter */])
```

- [ ] **Step 5: Track visible range for oscillator sync**

In the chart's `subscribeVisibleLogicalRangeChange` callback, add:

```typescript
setVisibleLogicalRange(range)
```

- [ ] **Step 6: Add Indicators button in header**

After the Draw button, add:

```typescript
<div className="relative">
  <button
    onClick={() => setIndicatorPanelOpen(!indicatorPanelOpen)}
    className={`flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[11px] transition-colors ${
      indicatorPanelOpen
        ? 'border-brand/60 bg-brand/10 text-text-primary'
        : 'border-border-primary text-text-muted hover:text-text-primary'
    }`}
    title="Indicators"
  >
    <BarChart2 size={10} />
    <span className="hidden md:inline">Indicators</span>
  </button>
  {indicatorPanelOpen && (
    <IndicatorPanel
      indicators={indicators}
      onToggle={toggleIndicator}
      onClose={() => setIndicatorPanelOpen(false)}
    />
  )}
</div>
<div className="mx-1 h-3 w-px bg-border-primary opacity-50" />
```

- [ ] **Step 7: Render oscillator panes below chart container**

After the chart container div but still inside the flex column, render enabled oscillators:

```typescript
{indicators
  .filter((ind) => ind.enabled && OSCILLATOR_INDICATORS.includes(ind.type))
  .map((ind) => {
    const raw = rawCandlesRef.current
    let data: { time: number; value: number }[] = []
    let extraLines: { data: { time: number; value: number }[]; color: string }[] | undefined
    let histogram: { time: number; value: number }[] | undefined
    let currentValue: number | null = null

    if (ind.type === 'rsi') {
      data = computeRSI(raw, ind.params.period)
      currentValue = data.length > 0 ? data[data.length - 1].value : null
    } else if (ind.type === 'macd') {
      const macdData = computeMACD(raw, ind.params.fast, ind.params.slow, ind.params.signal)
      data = macdData.map((d) => ({ time: d.time, value: d.macd }))
      extraLines = [{ data: macdData.map((d) => ({ time: d.time, value: d.signal })), color: '#e53935' }]
      histogram = macdData.map((d) => ({ time: d.time, value: d.histogram }))
      currentValue = macdData.length > 0 ? macdData[macdData.length - 1].macd : null
    } else if (ind.type === 'adx') {
      const adxData = computeADX(raw, ind.params.period)
      data = adxData.map((d) => ({ time: d.time, value: d.adx }))
      extraLines = [
        { data: adxData.map((d) => ({ time: d.time, value: d.plusDI })), color: '#4caf50' },
        { data: adxData.map((d) => ({ time: d.time, value: d.minusDI })), color: '#e53935' },
      ]
      currentValue = adxData.length > 0 ? adxData[adxData.length - 1].adx : null
    }

    return (
      <OscillatorPane
        key={ind.id}
        config={ind}
        data={data}
        extraLines={extraLines}
        histogram={histogram}
        expanded={oscillatorPaneState[ind.id] !== false}
        currentValue={currentValue}
        visibleRange={visibleLogicalRange}
        onToggleExpanded={() => setOscillatorPaneExpanded(ind.id, oscillatorPaneState[ind.id] === false)}
        onRemove={() => toggleIndicator(ind.id)}
      />
    )
  })}
```

- [ ] **Step 8: Verify compile**

Run: `npx tsc --noEmit`

- [ ] **Step 9: Visual verification**

Run dev server, open browser. Verify:
- Indicators button appears in header
- Clicking opens dropdown with Overlay/Oscillator sections
- Toggling EMA on shows a line on chart
- Toggling RSI on shows collapsible sub-pane below chart
- Pane collapse/expand works
- X button removes indicator

- [ ] **Step 10: Commit**

```bash
git add src/components/NiftyChart.tsx
git commit -m "feat: integrate indicator system — overlay rendering + oscillator panes"
```

---

## Chunk 7: Drawing Interaction & Context Menu

### Task 29: Drawing Context Menu

**Files:**
- Create: `src/components/chart/DrawingContextMenu.tsx`

- [ ] **Step 1: Create the context menu component**

A small popover for changing drawing color, line width, line style, or deleting. Positioned absolutely near the drawing.

```typescript
// src/components/chart/DrawingContextMenu.tsx
import { memo, useEffect, useRef } from 'react'
import { Trash2 } from 'lucide-react'
import type { DrawingStyle } from '../../lib/chart/types'

interface Props {
  x: number
  y: number
  style: DrawingStyle
  onChangeStyle: (updates: Partial<DrawingStyle>) => void
  onDelete: () => void
  onClose: () => void
}

const COLORS = ['#6366f1', '#f59e0b', '#4caf50', '#e53935', '#06b6d4', '#ec4899', '#8b5cf6', '#fff']
const WIDTHS: (1 | 2 | 3)[] = [1, 2, 3]

export const DrawingContextMenu = memo(function DrawingContextMenu({
  x, y, style, onChangeStyle, onDelete, onClose,
}: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  return (
    <div
      ref={ref}
      className="absolute z-40 w-[160px] rounded-lg border border-[#3a3a3a] bg-[#222] p-2 shadow-[0_8px_24px_rgba(0,0,0,0.5)]"
      style={{ left: x, top: y }}
    >
      {/* Colors */}
      <div className="mb-2 flex gap-1">
        {COLORS.map((c) => (
          <button
            key={c}
            onClick={() => onChangeStyle({ color: c })}
            className={`h-5 w-5 rounded-full border-2 transition-transform ${
              style.color === c ? 'scale-110 border-white' : 'border-transparent hover:scale-105'
            }`}
            style={{ backgroundColor: c }}
          />
        ))}
      </div>
      {/* Width */}
      <div className="mb-2 flex items-center gap-1">
        {WIDTHS.map((w) => (
          <button
            key={w}
            onClick={() => onChangeStyle({ lineWidth: w })}
            className={`flex h-6 flex-1 items-center justify-center rounded text-[10px] transition-colors ${
              style.lineWidth === w ? 'bg-brand/20 text-brand' : 'bg-[#2a2a2a] text-[#888] hover:text-[#ccc]'
            }`}
          >
            {w}px
          </button>
        ))}
      </div>
      {/* Style */}
      <div className="mb-2 flex items-center gap-1">
        {(['solid', 'dashed', 'dotted'] as const).map((s) => (
          <button
            key={s}
            onClick={() => onChangeStyle({ lineStyle: s })}
            className={`flex h-6 flex-1 items-center justify-center rounded text-[10px] transition-colors ${
              style.lineStyle === s ? 'bg-brand/20 text-brand' : 'bg-[#2a2a2a] text-[#888] hover:text-[#ccc]'
            }`}
          >
            {s}
          </button>
        ))}
      </div>
      {/* Delete */}
      <button
        onClick={onDelete}
        className="flex w-full items-center justify-center gap-1 rounded bg-[#2a2a2a] py-1 text-[10px] text-[#e53935] transition-colors hover:bg-[#e53935]/10"
      >
        <Trash2 size={10} /> Delete
      </button>
    </div>
  )
})
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/components/chart/DrawingContextMenu.tsx
git commit -m "feat: add DrawingContextMenu for editing drawing style"
```

### Task 30: Add Keyboard Shortcuts for Drawings

**Files:**
- Modify: `src/hooks/useKeyboardShortcuts.ts`

- [ ] **Step 1: Add drawing shortcuts**

In the keyboard handler, add cases for `-`, `|` (Shift+\), `T`, `Delete`/`Backspace` when chart is focused and no text input is active. These should call the store's `setActiveTool` and `removeDrawing` actions.

```typescript
// After existing shortcut cases:
case '-': {
  if (drawingToolbar) setActiveTool(activeTool === 'hline' ? null : 'hline')
  break
}
case '|': {
  if (drawingToolbar) setActiveTool(activeTool === 'vline' ? null : 'vline')
  break
}
// Note: 'T' conflicts with nothing in current shortcuts (t is not mapped)
```

- [ ] **Step 2: Verify compile, commit**

```bash
npx tsc --noEmit
git add src/hooks/useKeyboardShortcuts.ts
git commit -m "feat: add keyboard shortcuts for drawing tools"
```

### Task 31: Final Integration — Drawing Selection, Drag, Context Menu in NiftyChart

**Files:**
- Modify: `src/components/NiftyChart.tsx`

This is the most complex integration step. It adds:
1. Import DrawingContextMenu
2. Right-click handler to show context menu on drawings
3. Drawing selection on click (when no tool is active but toolbar is open)
4. Delete/Backspace to remove selected drawing
5. Context menu rendering

The hit-testing logic: on click/right-click, iterate through the current symbol's drawings, convert their points to pixel coordinates, check if the click is within a threshold distance. For horizontal lines, check |click.y - line.y| < 10. For trend lines, compute point-to-segment distance. This can be implemented incrementally — start with horizontal line hit-testing, then generalize.

- [ ] **Step 1: Add context menu state and handler**

```typescript
const [drawingContextMenu, setDrawingContextMenu] = useState<{
  drawingId: string
  x: number
  y: number
} | null>(null)
```

- [ ] **Step 2: Add right-click handler on chart container**

```typescript
onContextMenu={(e) => {
  if (!drawingToolbar) return
  e.preventDefault()
  // Hit-test drawings at click position
  const rect = containerRef.current?.getBoundingClientRect()
  if (!rect || !seriesRef.current) return
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  const symbol = chartQuote?.symbol ?? 'NIFTY 50'
  const symbolDrawings = drawings[symbol] ?? []

  for (const drawing of symbolDrawings) {
    // Simple hit-test: check if click is near the drawing
    if (drawing.type === 'hline') {
      const lineY = seriesRef.current.priceToCoordinate(drawing.points[0].price)
      if (lineY !== null && Math.abs(y - lineY) < 12) {
        setDrawingContextMenu({ drawingId: drawing.id, x: e.clientX - rect.left, y: e.clientY - rect.top })
        setSelectedDrawingId(drawing.id)
        return
      }
    }
    // Add more hit-test cases for other drawing types as needed
  }
}}
```

- [ ] **Step 3: Render context menu and handle actions**

Inside the chart container:

```typescript
{drawingContextMenu && (() => {
  const symbol = chartQuote?.symbol ?? 'NIFTY 50'
  const drawing = (drawings[symbol] ?? []).find((d) => d.id === drawingContextMenu.drawingId)
  if (!drawing) return null
  return (
    <DrawingContextMenu
      x={drawingContextMenu.x}
      y={drawingContextMenu.y}
      style={drawing.style}
      onChangeStyle={(updates) => updateDrawing(symbol, drawing.id, { style: { ...drawing.style, ...updates } })}
      onDelete={() => {
        removeDrawing(symbol, drawing.id)
        setDrawingContextMenu(null)
      }}
      onClose={() => setDrawingContextMenu(null)}
    />
  )
})()}
```

- [ ] **Step 4: Add Delete/Backspace handler**

In the existing keyboard handler for the chart:

```typescript
if ((e.key === 'Delete' || e.key === 'Backspace') && selectedDrawingId) {
  const symbol = chartQuote?.symbol ?? 'NIFTY 50'
  removeDrawing(symbol, selectedDrawingId)
}
```

- [ ] **Step 5: Verify compile**

Run: `npx tsc --noEmit`

- [ ] **Step 6: Visual verification**

Run dev server:
- Draw a horizontal line
- Right-click it → context menu appears
- Change color → line updates
- Click Delete → line removed
- Draw a line, select it, press Delete → removed

- [ ] **Step 7: Commit**

```bash
git add src/components/NiftyChart.tsx
git commit -m "feat: add drawing selection, context menu, and delete interaction"
```

---

## Chunk 8: Polish & Final Verification

### Task 32: Add .superpowers to .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add `.superpowers/` to gitignore if not already present**

```bash
echo '.superpowers/' >> .gitignore
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .superpowers to gitignore"
```

### Task 33: Full Compile & Visual Smoke Test

- [ ] **Step 1: Full TypeScript check**

Run: `npx tsc --noEmit`
Expected: clean, no errors

- [ ] **Step 2: Dev server smoke test**

Run dev server, open browser, verify all of the following:
- [ ] Chart loads normally with no regressions
- [ ] Draw button appears, toggles toolbar
- [ ] All 7 drawing tools work (click to place)
- [ ] Horizontal line renders across full chart width
- [ ] Drawings persist across page reload (localStorage)
- [ ] Drawings are symbol-specific (NIFTY vs option)
- [ ] Drawings show on all timeframes
- [ ] Right-click drawing opens context menu
- [ ] Color/width/style changes work
- [ ] Delete drawing works (context menu and Delete key)
- [ ] Indicators button opens dropdown
- [ ] Toggling EMA/SMA shows line on chart
- [ ] Toggling RSI shows collapsible sub-pane
- [ ] Oscillator pane collapses/expands
- [ ] Oscillator time axis syncs with main chart
- [ ] MACD shows histogram + two lines
- [ ] Mobile timeframes on separate row (< 600px)
- [ ] Watermark displays at correct size

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address issues found during smoke testing"
```
