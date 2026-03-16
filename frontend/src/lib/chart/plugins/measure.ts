import type { Drawing } from '../types'
import { BaseDrawingPlugin } from './base-drawing'

// 2 points: measure box showing price diff, % change
export class MeasurePlugin extends BaseDrawingPlugin {
  constructor(drawing: Drawing) {
    super(drawing)
  }

  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    const [p1, p2] = this.drawing.points
    if (!p1 || !p2) return

    const px1 = this.pointToPixel(p1)
    const px2 = this.pointToPixel(p2)
    if (!px1 || !px2) return

    const { color, lineWidth, fillOpacity = 0.15 } = this.drawing.style

    const x = Math.min(px1.x, px2.x)
    const y = Math.min(px1.y, px2.y)
    const w = Math.abs(px2.x - px1.x)
    const h = Math.abs(px2.y - px1.y)

    const priceDiff = p2.price - p1.price
    const pricePct = (priceDiff / p1.price) * 100
    const sign = priceDiff >= 0 ? '+' : ''
    const label = `${sign}${priceDiff.toFixed(2)} (${sign}${pricePct.toFixed(2)}%)`

    // Determine fill color based on direction (green up, red down)
    const fillColor = priceDiff >= 0
      ? `rgba(34,197,94,${fillOpacity})`
      : `rgba(239,68,68,${fillOpacity})`
    const borderColor = priceDiff >= 0 ? '#22c55e' : '#ef4444'

    ctx.save()

    // Fill
    ctx.fillStyle = fillColor
    ctx.fillRect(x, y, w, h)

    // Border
    ctx.strokeStyle = borderColor
    ctx.lineWidth = lineWidth
    ctx.setLineDash([4, 3])
    ctx.strokeRect(x, y, w, h)

    // Horizontal dashed lines at each price endpoint
    ctx.strokeStyle = color
    ctx.lineWidth = 1
    ctx.setLineDash([3, 3])
    ctx.beginPath()
    ctx.moveTo(x, px1.y)
    ctx.lineTo(x + w, px1.y)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(x, px2.y)
    ctx.lineTo(x + w, px2.y)
    ctx.stroke()

    // Label centered in box
    ctx.setLineDash([])
    ctx.fillStyle = borderColor
    ctx.font = 'bold 11px monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    if (w > 60 && h > 20) {
      ctx.fillText(label, x + w / 2, y + h / 2)
    } else {
      // Not enough space — draw label above box
      ctx.textBaseline = 'bottom'
      ctx.fillText(label, x + w / 2, y - 4)
    }

    ctx.restore()
  }
}
