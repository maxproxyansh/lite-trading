import type { Drawing } from '../types'
import { BaseDrawingPlugin } from './base-drawing'

export class HorizontalLinePlugin extends BaseDrawingPlugin {
  constructor(drawing: Drawing) {
    super(drawing)
  }

  drawOnCanvas(ctx: CanvasRenderingContext2D, width: number, _height: number): void {
    const point = this.drawing.points[0]
    if (!point) return

    const y = this.priceToY(point.price)
    if (y === null) return

    const { color, lineWidth } = this.drawing.style
    const dash = this.getLineDash()

    ctx.save()
    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    if (dash.length) ctx.setLineDash(dash)

    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()

    // Price label on right side
    ctx.fillStyle = color
    ctx.font = '11px monospace'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'bottom'
    ctx.fillText(point.price.toFixed(2), width - 4, y - 2)

    ctx.restore()
  }
}
