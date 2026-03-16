import { BaseDrawingPlugin } from './base-drawing'

// 3 points: p1 & p2 define the baseline, p3 defines the parallel offset
export class ChannelPlugin extends BaseDrawingPlugin {
  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    const [p1, p2, p3] = this.drawing.points
    if (!p1 || !p2 || !p3) return

    const px1 = this.pointToPixel(p1)
    const px2 = this.pointToPixel(p2)
    if (!px1 || !px2) return

    // Compute the parallel line by shifting each baseline point by the price offset
    const priceDiff = p3.price - p1.price
    const y3 = this.priceToY(p1.price + priceDiff)
    const y4 = this.priceToY(p2.price + priceDiff)
    if (y3 === null || y4 === null) return

    const { color, lineWidth, fillOpacity = 0.12 } = this.drawing.style

    ctx.save()

    // Fill between the two lines
    ctx.fillStyle = colorWithAlpha(color, fillOpacity)
    ctx.beginPath()
    ctx.moveTo(px1.x, px1.y)
    ctx.lineTo(px2.x, px2.y)
    ctx.lineTo(px2.x, y4)
    ctx.lineTo(px1.x, y3)
    ctx.closePath()
    ctx.fill()

    // Baseline (solid)
    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    ctx.setLineDash([])
    ctx.beginPath()
    ctx.moveTo(px1.x, px1.y)
    ctx.lineTo(px2.x, px2.y)
    ctx.stroke()

    // Parallel line (solid)
    ctx.beginPath()
    ctx.moveTo(px1.x, y3)
    ctx.lineTo(px2.x, y4)
    ctx.stroke()

    // Midline (dashed)
    const midY1 = (px1.y + y3) / 2
    const midY2 = (px2.y + y4) / 2
    ctx.strokeStyle = colorWithAlpha(color, 0.5)
    ctx.lineWidth = Math.max(lineWidth - 0.5, 0.5)
    ctx.setLineDash([6, 4])
    ctx.beginPath()
    ctx.moveTo(px1.x, midY1)
    ctx.lineTo(px2.x, midY2)
    ctx.stroke()

    // Anchor dots at endpoints
    ctx.setLineDash([])
    ctx.strokeStyle = color
    ctx.lineWidth = 1.5
    ctx.fillStyle = '#1a1a1a'
    for (const [x, y] of [[px1.x, px1.y], [px2.x, px2.y], [px1.x, y3], [px2.x, y4]] as [number, number][]) {
      ctx.beginPath()
      ctx.arc(x, y, 3.5, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    }

    ctx.restore()
  }
}

function colorWithAlpha(color: string, alpha: number): string {
  // Handle rgba() format
  if (color.startsWith('rgba')) {
    return color.replace(/[\d.]+\)$/, `${alpha})`)
  }
  // Handle rgb() format
  if (color.startsWith('rgb(')) {
    return color.replace('rgb(', 'rgba(').replace(')', `,${alpha})`)
  }
  // Handle hex
  if (color.startsWith('#')) {
    const hex = color.length === 4
      ? `#${color[1]}${color[1]}${color[2]}${color[2]}${color[3]}${color[3]}`
      : color
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return `rgba(${r},${g},${b},${alpha})`
  }
  return color
}
