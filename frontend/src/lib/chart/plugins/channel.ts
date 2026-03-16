import type { Drawing } from '../types'
import { BaseDrawingPlugin } from './base-drawing'

// 3 points: p1 & p2 define the baseline, p3 defines the parallel offset channel line
export class ChannelPlugin extends BaseDrawingPlugin {
  constructor(drawing: Drawing) {
    super(drawing)
  }

  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    const [p1, p2, p3] = this.drawing.points
    if (!p1 || !p2 || !p3) return

    const px1 = this.pointToPixel(p1)
    const px2 = this.pointToPixel(p2)
    // p3 defines the price offset — use same x-coords as p1/p2 but shifted y
    const offsetY = this.priceToY(p3.price)
    const baseY1 = this.priceToY(p1.price)
    const baseY2 = this.priceToY(p2.price)

    if (!px1 || !px2 || offsetY === null || baseY1 === null || baseY2 === null) return

    const priceDiff = p3.price - p1.price
    const y3 = px1.y + (this.priceToY(p1.price + priceDiff) !== null
      ? (this.priceToY(p1.price + priceDiff)! - px1.y)
      : 0)
    const y4 = px2.y + (this.priceToY(p2.price + priceDiff) !== null
      ? (this.priceToY(p2.price + priceDiff)! - px2.y)
      : 0)

    const { color, lineWidth, fillOpacity = 0.1 } = this.drawing.style
    const dash = this.getLineDash()

    ctx.save()
    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    if (dash.length) ctx.setLineDash(dash)

    // Baseline
    ctx.beginPath()
    ctx.moveTo(px1.x, px1.y)
    ctx.lineTo(px2.x, px2.y)
    ctx.stroke()

    // Parallel offset line
    ctx.beginPath()
    ctx.moveTo(px1.x, y3)
    ctx.lineTo(px2.x, y4)
    ctx.stroke()

    // Fill between the two lines
    ctx.setLineDash([])
    const fillColor = hexToRgba(color, fillOpacity)
    ctx.fillStyle = fillColor
    ctx.beginPath()
    ctx.moveTo(px1.x, px1.y)
    ctx.lineTo(px2.x, px2.y)
    ctx.lineTo(px2.x, y4)
    ctx.lineTo(px1.x, y3)
    ctx.closePath()
    ctx.fill()

    ctx.restore()
  }
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}
