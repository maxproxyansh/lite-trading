import type { Drawing } from '../types'
import { BaseDrawingPlugin } from './base-drawing'

// 2 points: top-left and bottom-right corners
export class RectanglePlugin extends BaseDrawingPlugin {
  constructor(drawing: Drawing) {
    super(drawing)
  }

  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    const [p1, p2] = this.drawing.points
    if (!p1 || !p2) return

    const px1 = this.pointToPixel(p1)
    const px2 = this.pointToPixel(p2)
    if (!px1 || !px2) return

    const { color, lineWidth, fillOpacity = 0.1 } = this.drawing.style
    const dash = this.getLineDash()

    const x = Math.min(px1.x, px2.x)
    const y = Math.min(px1.y, px2.y)
    const w = Math.abs(px2.x - px1.x)
    const h = Math.abs(px2.y - px1.y)

    ctx.save()

    // Fill
    ctx.fillStyle = hexToRgba(color, fillOpacity)
    ctx.fillRect(x, y, w, h)

    // Border
    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    if (dash.length) ctx.setLineDash(dash)
    ctx.strokeRect(x, y, w, h)

    ctx.restore()
  }
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}
