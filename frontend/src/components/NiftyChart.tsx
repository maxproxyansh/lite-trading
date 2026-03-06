import { useEffect, useRef, useState } from 'react'
import { createChart } from 'lightweight-charts'
import type { CandlestickData, IChartApi, ISeriesApi, Time } from 'lightweight-charts'

import { fetchCandles } from '../lib/api'

const TIMEFRAMES = ['1m', '5m', '15m', '1h', 'D'] as const

export default function NiftyChart() {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const [timeframe, setTimeframe] = useState<(typeof TIMEFRAMES)[number]>('15m')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#1a1a2e' }, textColor: '#5e5e76' },
      grid: { vertLines: { color: '#2a2a44' }, horzLines: { color: '#2a2a44' } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#333350' },
      timeScale: { borderColor: '#333350', timeVisible: true, secondsVisible: false },
    })
    const series = chart.addCandlestickSeries({
      upColor: '#4caf50',
      downColor: '#e25c4f',
      borderUpColor: '#4caf50',
      borderDownColor: '#e25c4f',
      wickUpColor: '#4caf50',
      wickDownColor: '#e25c4f',
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
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [timeframe])

  return (
    <div className="relative flex h-full flex-col bg-bg-primary">
      {/* Timeframe bar */}
      <div className="flex items-center gap-1 border-b border-border-secondary px-3 py-1.5">
        <span className="mr-2 text-xs font-medium text-text-primary">NIFTY 50</span>
        <div className="flex items-center gap-0.5 rounded bg-bg-secondary p-0.5">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => {
                setLoading(true)
                setTimeframe(tf)
              }}
              className={`rounded px-2 py-1 text-[11px] font-medium transition-colors ${
                timeframe === tf
                  ? 'bg-signal text-white'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div ref={containerRef} className="relative flex-1">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-bg-primary/80">
            <div className="h-6 w-6 rounded-full border-2 border-signal border-t-transparent animate-spin" />
          </div>
        )}
      </div>
    </div>
  )
}
