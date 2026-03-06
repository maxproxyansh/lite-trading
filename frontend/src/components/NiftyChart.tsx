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
      layout: { background: { color: '#161616' }, textColor: '#8F98A3' },
      grid: { vertLines: { color: '#262626' }, horzLines: { color: '#262626' } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#2E2E2E' },
      timeScale: { borderColor: '#2E2E2E', timeVisible: true, secondsVisible: false },
    })
    const series = chart.addCandlestickSeries({
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderUpColor: '#16a34a',
      borderDownColor: '#dc2626',
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626',
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
    <section className="relative flex h-full flex-col rounded-2xl border border-border-primary bg-bg-secondary">
      <div className="flex items-center gap-2 border-b border-border-primary px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-text-primary">NIFTY 50</div>
          <div className="text-[11px] text-text-muted">Intraday and daily candles via Dhan</div>
        </div>
        <div className="ml-auto flex items-center gap-1 rounded-xl bg-bg-primary p-1">
          {TIMEFRAMES.map((item) => (
            <button
              key={item}
              onClick={() => {
                setLoading(true)
                setTimeframe(item)
              }}
              className={`rounded-lg px-3 py-1.5 text-[11px] font-medium ${
                timeframe === item ? 'bg-signal text-white' : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>
      <div ref={containerRef} className="relative flex-1">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-bg-secondary/70">
            <div className="h-8 w-8 rounded-full border-2 border-signal border-t-transparent animate-spin" />
          </div>
        )}
      </div>
    </section>
  )
}
