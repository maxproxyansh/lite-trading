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

  sync(drawings: Drawing[]): void {
    const drawingIds = new Set(drawings.map((d) => d.id))
    for (const [id, plugin] of this._plugins) {
      if (!drawingIds.has(id)) {
        this._series.detachPrimitive(plugin)
        this._plugins.delete(id)
      }
    }
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

  destroy(): void {
    for (const [, plugin] of this._plugins) {
      this._series.detachPrimitive(plugin)
    }
    this._plugins.clear()
  }
}
