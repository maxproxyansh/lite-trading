import type { Drawing } from '../types'
import { BaseDrawingPlugin } from './base-drawing'

export class TrendlinePlugin extends BaseDrawingPlugin {
  constructor(drawing: Drawing) {
    super(drawing)
  }

  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    const [p1, p2] = this.drawing.points
    if (!p1 || !p2) return

    const px1 = this.pointToPixel(p1)
    const px2 = this.pointToPixel(p2)
    if (!px1 || !px2) return

    const { color, lineWidth } = this.drawing.style
    const dash = this.getLineDash()

    ctx.save()
    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    if (dash.length) ctx.setLineDash(dash)

    ctx.beginPath()
    ctx.moveTo(px1.x, px1.y)
    ctx.lineTo(px2.x, px2.y)
    ctx.stroke()

    // Hollow anchor circles at endpoints (TradingView style)
    ctx.setLineDash([])
    ctx.strokeStyle = color
    ctx.lineWidth = 1.5
    ctx.fillStyle = '#1a1a1a'
    for (const p of [px1, px2]) {
      ctx.beginPath()
      ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    }

    ctx.restore()
  }
}
