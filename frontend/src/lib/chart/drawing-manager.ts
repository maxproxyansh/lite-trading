import type { IChartApi, ISeriesApi, IPriceLine } from 'lightweight-charts'
import type { Drawing } from './types'
import type { BaseDrawingPlugin } from './plugins'
import { createDrawingPlugin } from './plugins'

const LINE_STYLE_MAP = { solid: 0, dashed: 2, dotted: 3 } as const

export class DrawingManager {
  private _chart: IChartApi
  private _series: ISeriesApi<'Candlestick'>
  private _plugins: Map<string, BaseDrawingPlugin> = new Map()
  private _priceLines: Map<string, IPriceLine> = new Map()

  constructor(chart: IChartApi, series: ISeriesApi<'Candlestick'>) {
    this._chart = chart
    this._series = series
  }

  sync(drawings: Drawing[]): void {
    const drawingIds = new Set(drawings.map((d) => d.id))

    // Remove stale price lines (hlines)
    for (const [id, line] of this._priceLines) {
      if (!drawingIds.has(id)) {
        this._series.removePriceLine(line)
        this._priceLines.delete(id)
      }
    }

    // Remove stale plugins (non-hline drawings)
    for (const [id, plugin] of this._plugins) {
      if (!drawingIds.has(id)) {
        this._series.detachPrimitive(plugin)
        this._plugins.delete(id)
      }
    }

    // Add or update drawings
    for (const drawing of drawings) {
      if (drawing.type === 'hline') {
        this._syncHLine(drawing)
      } else {
        this._syncPlugin(drawing)
      }
    }

    // Force chart repaint
    this._chart.timeScale().applyOptions({})
  }

  private _syncHLine(drawing: Drawing): void {
    const existing = this._priceLines.get(drawing.id)
    const opts = {
      price: drawing.points[0].price,
      color: drawing.style.color,
      lineWidth: drawing.style.lineWidth as 1 | 2 | 3 | 4,
      lineStyle: LINE_STYLE_MAP[drawing.style.lineStyle] ?? 0,
      axisLabelVisible: true,
      title: '',
    }
    if (existing) {
      existing.applyOptions(opts)
    } else {
      const line = this._series.createPriceLine(opts)
      this._priceLines.set(drawing.id, line)
    }
  }

  private _syncPlugin(drawing: Drawing): void {
    const existing = this._plugins.get(drawing.id)
    if (existing) {
      existing.updateDrawing(drawing)
    } else {
      const plugin = createDrawingPlugin(drawing)
      this._series.attachPrimitive(plugin)
      this._plugins.set(drawing.id, plugin)
    }
  }

  destroy(): void {
    for (const [, line] of this._priceLines) {
      this._series.removePriceLine(line)
    }
    this._priceLines.clear()
    for (const [, plugin] of this._plugins) {
      this._series.detachPrimitive(plugin)
    }
    this._plugins.clear()
  }
}
