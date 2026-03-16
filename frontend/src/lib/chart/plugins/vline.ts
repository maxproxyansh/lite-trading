import type { Drawing } from '../types'
import { BaseDrawingPlugin } from './base-drawing'

export class VerticalLinePlugin extends BaseDrawingPlugin {
  constructor(drawing: Drawing) {
    super(drawing)
  }

  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, height: number): void {
    const point = this.drawing.points[0]
    if (!point) return

    const x = this.timeToX(point.time)
    if (x === null) return

    const { color, lineWidth } = this.drawing.style
    const dash = this.getLineDash()

    ctx.save()
    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    if (dash.length) ctx.setLineDash(dash)

    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()

    ctx.restore()
  }
}
