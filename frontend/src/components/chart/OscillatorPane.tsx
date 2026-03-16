import { memo, useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { createChart } from 'lightweight-charts'
import type { IChartApi, LogicalRange, Time } from 'lightweight-charts'
import type { IndicatorConfig } from '../../lib/chart/types'

interface Props {
  config: IndicatorConfig
  data: { time: number; value: number }[]
  extraLines?: { data: { time: number; value: number }[]; color: string }[]
  histogram?: { time: number; value: number }[]
  expanded: boolean
  currentValue: number | null
  visibleRange: LogicalRange | null
  onToggleExpanded: () => void
  onRemove: () => void
}

const LABELS: Record<string, string> = { rsi: 'RSI', macd: 'MACD', adx: 'ADX' }
const IST_OFFSET_SECONDS = 5.5 * 60 * 60

export const OscillatorPane = memo(function OscillatorPane({
  config, data, extraLines, histogram, expanded, currentValue, visibleRange, onToggleExpanded, onRemove,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const isSyncingRef = useRef(false)

  useEffect(() => {
    if (!expanded || !containerRef.current) return
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth, height: 80,
      layout: { background: { color: '#1a1a1a' }, textColor: '#555', fontSize: 9 },
      grid: { vertLines: { visible: false }, horzLines: { color: '#222' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { visible: false, borderVisible: false },
      crosshair: { mode: 0 },
      handleScroll: false, handleScale: false,
    })
    const mainSeries = chart.addLineSeries({
      color: config.color, lineWidth: config.lineWidth,
      priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
    })
    mainSeries.setData(data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.value })))
    if (extraLines) {
      for (const line of extraLines) {
        const s = chart.addLineSeries({ color: line.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
        s.setData(line.data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.value })))
      }
    }
    if (histogram) {
      const h = chart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false, priceScaleId: '' })
      h.setData(histogram.map((d) => ({
        time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.value,
        color: d.value >= 0 ? 'rgba(76,175,80,0.5)' : 'rgba(229,57,53,0.5)',
      })))
    }
    chartRef.current = chart
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width
      if (w > 0) chart.applyOptions({ width: w })
    })
    ro.observe(containerRef.current)
    return () => { ro.disconnect(); chart.remove(); chartRef.current = null }
  }, [expanded]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!chartRef.current || !visibleRange || isSyncingRef.current) return
    isSyncingRef.current = true
    chartRef.current.timeScale().setVisibleLogicalRange(visibleRange)
    requestAnimationFrame(() => { isSyncingRef.current = false })
  }, [visibleRange])

  const paramStr = Object.values(config.params).join(', ')

  return (
    <div className="border-t border-[#2a2a2a]">
      <div className="flex cursor-pointer items-center px-2 py-0.5" style={{ height: 22, background: '#1e1e1e' }} onClick={onToggleExpanded}>
        <span className="mr-1 text-[10px] text-[#888]">{expanded ? '▼' : '▶'}</span>
        <span className="text-[10px] font-medium text-[#999]">{LABELS[config.type] ?? config.type}</span>
        <span className="ml-1 text-[10px] text-[#666]">({paramStr})</span>
        <span className="ml-auto tabular-nums text-[10px] font-semibold text-brand">{currentValue !== null ? currentValue.toFixed(1) : '—'}</span>
        <button onClick={(e) => { e.stopPropagation(); onRemove() }} className="ml-2 text-[#555] transition-colors hover:text-[#e53935]"><X size={10} /></button>
      </div>
      {expanded && <div ref={containerRef} style={{ height: 80 }} />}
    </div>
  )
})
