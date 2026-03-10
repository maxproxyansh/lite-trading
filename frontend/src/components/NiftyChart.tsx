import { useEffect, useRef, useState } from 'react'
import { createChart } from 'lightweight-charts'
import type { CandlestickData, IChartApi, ISeriesApi, Time } from 'lightweight-charts'

import { fetchCandles } from '../lib/api'

const TIMEFRAMES = ['1m', '5m', '15m', '1h', 'D'] as const

function getChartColors() {
  const styles = getComputedStyle(document.documentElement)
  const bgPrimary = styles.getPropertyValue('--color-bg-primary').trim() || '#1a1a1a'
  const bgSecondary = styles.getPropertyValue('--color-bg-secondary').trim() || '#252525'
  const textMuted = styles.getPropertyValue('--color-text-muted').trim() || '#666666'
  const borderPrimary = styles.getPropertyValue('--color-border-primary').trim() || '#363636'
  const bullColor = styles.getPropertyValue('--color-candle-bull').trim() || '#4caf50'
  const bearColor = styles.getPropertyValue('--color-candle-bear').trim() || '#e53935'
  return { bgPrimary, bgSecondary, textMuted, borderPrimary, bullColor, bearColor }
}

export default function NiftyChart() {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const [timeframe, setTimeframe] = useState<(typeof TIMEFRAMES)[number]>('15m')
  const [loading, setLoading] = useState(true)
  const [candleCount, setCandleCount] = useState(0)

  useEffect(() => {
    if (!containerRef.current) return
    const colors = getChartColors()
    const chart = createChart(containerRef.current, {
      layout: { background: { color: colors.bgPrimary }, textColor: colors.textMuted },
      grid: { vertLines: { color: colors.bgSecondary }, horzLines: { color: colors.bgSecondary } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: colors.borderPrimary },
      timeScale: { borderColor: colors.borderPrimary, timeVisible: true, secondsVisible: false },
    })
    const series = chart.addCandlestickSeries({
      upColor: colors.bullColor,
      downColor: colors.bearColor,
      borderUpColor: colors.bullColor,
      borderDownColor: colors.bearColor,
      wickUpColor: colors.bullColor,
      wickDownColor: colors.bearColor,
    })
    chartRef.current = chart
    seriesRef.current = series

    const observer = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight })
      }
    })
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [])

  useEffect(() => {
    let active = true
    fetchCandles(timeframe)
      .then((response) => {
        if (!active) return
        const candles: CandlestickData[] = response.candles.map((candle) => ({
          time: candle.time as Time,
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
        }))
        seriesRef.current?.setData(candles)
        chartRef.current?.timeScale().fitContent()
        setCandleCount(candles.length)
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [timeframe])

  return (
    <div className="relative flex h-full flex-col bg-bg-primary">
      {/* Timeframe bar */}
      <div className="flex items-center gap-1 border-b border-border-secondary px-3 py-1">
        <span className="mr-2 text-[11px] text-text-muted">NIFTY 50</span>
        <div className="flex items-center gap-0.5">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => {
                setLoading(true)
                setTimeframe(tf)
              }}
              className={`px-2 py-0.5 text-[11px] transition-colors ${
                timeframe === tf
                  ? 'bg-brand text-bg-primary rounded-sm'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div ref={containerRef} className="relative flex-1 min-h-0">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-bg-primary/80">
            <div className="h-6 w-6 rounded-full border-2 border-signal border-t-transparent animate-spin" />
          </div>
        )}
        {candleCount === 0 && !loading && (
          <div className="absolute inset-0 flex items-center justify-center text-text-muted text-sm">
            Market closed
          </div>
        )}
      </div>
    </div>
  )
}
