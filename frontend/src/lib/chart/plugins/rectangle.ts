import { BaseDrawingPlugin } from './base-drawing'

export class RectanglePlugin extends BaseDrawingPlugin {
  drawOnCanvas(ctx: CanvasRenderingContext2D, _width: number, _height: number): void {
    const [p1, p2] = this.drawing.points
    if (!p1 || !p2) return

    const px1 = this.pointToPixel(p1)
    const px2 = this.pointToPixel(p2)
    if (!px1 || !px2) return

    const { color, lineWidth, fillOpacity = 0.12 } = this.drawing.style
    const dash = this.getLineDash()

    const x = Math.min(px1.x, px2.x)
    const y = Math.min(px1.y, px2.y)
    const w = Math.abs(px2.x - px1.x)
    const h = Math.abs(px2.y - px1.y)

    ctx.save()

    // Fill
    ctx.fillStyle = colorWithAlpha(color, fillOpacity)
    ctx.fillRect(x, y, w, h)

    // Border
    ctx.strokeStyle = color
    ctx.lineWidth = lineWidth
    if (dash.length) ctx.setLineDash(dash)
    ctx.strokeRect(x, y, w, h)

    // Anchor dots at corners
    ctx.setLineDash([])
    ctx.strokeStyle = color
    ctx.lineWidth = 1.5
    ctx.fillStyle = '#1a1a1a'
    for (const [cx, cy] of [[px1.x, px1.y], [px2.x, px2.y], [px1.x, px2.y], [px2.x, px1.y]] as [number, number][]) {
      ctx.beginPath()
      ctx.arc(cx, cy, 3, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    }

    ctx.restore()
  }
}

function colorWithAlpha(color: string, alpha: number): string {
  if (color.startsWith('rgba')) return color.replace(/[\d.]+\)$/, `${alpha})`)
  if (color.startsWith('rgb(')) return color.replace('rgb(', 'rgba(').replace(')', `,${alpha})`)
  if (color.startsWith('#')) {
    const hex = color.length === 4 ? `#${color[1]}${color[1]}${color[2]}${color[2]}${color[3]}${color[3]}` : color
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return `rgba(${r},${g},${b},${alpha})`
  }
  return color
}
