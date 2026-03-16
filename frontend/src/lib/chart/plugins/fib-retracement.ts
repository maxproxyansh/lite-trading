import type { Drawing } from '../types'
import { BaseDrawingPlugin } from './base-drawing'

const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]

// 2 points: swing high (p1) and swing low (p2) — or vice versa
export class FibRetracementPlugin extends BaseDrawingPlugin {
  constructor(drawing: Drawing) {
    super(drawing)
  }

  drawOnCanvas(ctx: CanvasRenderingContext2D, width: number, _height: number): void {
    const [p1, p2] = this.drawing.points
    if (!p1 || !p2) return

    const x1 = this.timeToX(p1.time)
    const x2 = this.timeToX(p2.time)
    if (x1 === null || x2 === null) return

    const xLeft = Math.min(x1, x2)
    const xRight = Math.max(x1, x2)
    const drawWidth = xRight - xLeft > 0 ? xRight - xLeft : width

    const priceRange = p2.price - p1.price
    const { color, lineWidth, fillOpacity = 0.05 } = this.drawing.style
    const dash = this.getLineDash()

    ctx.save()
    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth

    for (let i = 0; i < FIB_LEVELS.length; i++) {
      const level = FIB_LEVELS[i]
      const price = p1.price + priceRange * level
      const y = this.priceToY(price)
      if (y === null) continue

      // Zone fill between consecutive levels
      if (i < FIB_LEVELS.length - 1) {
        const nextLevel = FIB_LEVELS[i + 1]
        const nextPrice = p1.price + priceRange * nextLevel
        const nextY = this.priceToY(nextPrice)
        if (nextY !== null) {
          const alpha = i % 2 === 0 ? fillOpacity : fillOpacity * 0.5
          ctx.fillStyle = hexToRgba(color, alpha)
          ctx.fillRect(xLeft, Math.min(y, nextY), drawWidth, Math.abs(nextY - y))
        }
      }

      // Horizontal line
      if (dash.length) ctx.setLineDash(dash)
      else ctx.setLineDash([])
      ctx.strokeStyle = adjustAlpha(color, level === 0 || level === 1 ? 1 : 0.7)
      ctx.beginPath()
      ctx.moveTo(xLeft, y)
      ctx.lineTo(xLeft + drawWidth, y)
      ctx.stroke()

      // Label
      ctx.fillStyle = color
      ctx.font = '10px monospace'
      ctx.textAlign = 'left'
      ctx.textBaseline = 'bottom'
      ctx.setLineDash([])
      ctx.fillText(`${(level * 100).toFixed(1)}% ${price.toFixed(2)}`, xLeft + 4, y - 2)
    }

    ctx.restore()
  }
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

function adjustAlpha(hex: string, alpha: number): string {
  return hexToRgba(hex, alpha)
}
