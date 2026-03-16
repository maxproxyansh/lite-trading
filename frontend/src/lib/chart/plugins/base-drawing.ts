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

class DrawingPaneView implements ISeriesPrimitivePaneView {
  private _plugin: BaseDrawingPlugin
  constructor(plugin: BaseDrawingPlugin) {
    this._plugin = plugin
  }
  renderer(): ISeriesPrimitivePaneRenderer {
    return new DrawingPaneRenderer(this._plugin)
  }
}

export abstract class BaseDrawingPlugin implements ISeriesPrimitive<Time> {
  drawing: Drawing
  protected _chart: IChartApi | null = null
  protected _series: ISeriesApi<'Candlestick'> | null = null
  private _paneViews: ISeriesPrimitivePaneView[]

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

  protected pointToPixel(point: DrawingPoint): { x: number; y: number } | null {
    if (!this._chart || !this._series) return null
    const x = this._chart.timeScale().timeToCoordinate(point.time as Time)
    const y = this._series.priceToCoordinate(point.price)
    if (x === null || y === null) return null
    return { x, y }
  }

  protected priceToY(price: number): number | null {
    if (!this._series) return null
    return this._series.priceToCoordinate(price)
  }

  protected timeToX(time: number): number | null {
    if (!this._chart) return null
    return this._chart.timeScale().timeToCoordinate(time as Time)
  }

  protected getLineDash(): number[] {
    switch (this.drawing.style.lineStyle) {
      case 'dashed': return [6, 4]
      case 'dotted': return [2, 3]
      default: return []
    }
  }

  abstract drawOnCanvas(ctx: CanvasRenderingContext2D, width: number, height: number): void
}
