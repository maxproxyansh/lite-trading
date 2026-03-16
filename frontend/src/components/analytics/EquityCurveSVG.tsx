import { useEffect, useRef, useState } from 'react'

type Props = {
  data: Array<{ label: string; value: number }>
  height?: number
}

export default function EquityCurveSVG({ data, height = 160 }: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const el = wrapperRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width)
      }
    })
    ro.observe(el)
    setWidth(el.clientWidth)
    return () => ro.disconnect()
  }, [])

  if (!data.length) {
    return (
      <div
        ref={wrapperRef}
        className="flex items-center justify-center text-text-muted text-xs"
        style={{ height }}
      >
        No equity data yet
      </div>
    )
  }

  if (width === 0) {
    return <div ref={wrapperRef} style={{ height }} />
  }

  const padX = 0
  const padY = 4
  const chartW = width - padX * 2
  const chartH = height - padY * 2

  const values = data.map((d) => d.value)
  const minV = Math.min(...values)
  const maxV = Math.max(...values)
  const rangeV = maxV - minV || 1

  const points = data.map((d, i) => {
    const x = padX + (data.length > 1 ? (i / (data.length - 1)) * chartW : chartW / 2)
    const y = padY + chartH - ((d.value - minV) / rangeV) * chartH
    return { x, y }
  })

  // Line path
  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')

  // Area path (close to bottom)
  const areaPath = `${linePath} L${points[points.length - 1].x},${padY + chartH} L${points[0].x},${padY + chartH} Z`

  // Baseline at first data point
  const baselineY = points[0].y

  return (
    <div ref={wrapperRef}>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="eq-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(56,126,209,0.12)" />
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>
        </defs>

        {/* Baseline */}
        <line
          x1={padX}
          y1={baselineY}
          x2={padX + chartW}
          y2={baselineY}
          stroke="#333"
          strokeWidth={1}
          strokeDasharray="4,3"
        />

        {/* Area fill */}
        <path d={areaPath} fill="url(#eq-grad)" />

        {/* Line */}
        <path d={linePath} fill="none" stroke="#387ed1" strokeWidth={1.5} />
      </svg>
    </div>
  )
}
