import { useEffect, useRef, useState } from 'react'
import { Bell, X } from 'lucide-react'
import { createChart, LineStyle } from 'lightweight-charts'
import type { CandlestickData, IChartApi, IPriceLine, ISeriesApi, LogicalRange, MouseEventParams, Time } from 'lightweight-charts'
import { useShallow } from 'zustand/react/shallow'

import { ApiError, createAlert, deleteAlert, fetchAlerts, fetchCandles, type AlertSummary, type Candle } from '../lib/api'
import { useStore } from '../store/useStore'

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

function timeframeSeconds(timeframe: (typeof TIMEFRAMES)[number]) {
  const map = {
    '1m': 60,
    '5m': 300,
    '15m': 900,
    '1h': 3600,
    D: 86400,
  } as const
  return map[timeframe]
}

function toChartCandles(candles: Candle[]) {
  return candles.map((candle) => ({
    time: candle.time as Time,
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
  }))
}

function mergeCandles(existing: CandlestickData<Time>[], incoming: CandlestickData<Time>[]) {
  const merged = new Map<number, CandlestickData<Time>>()
  for (const candle of existing) {
    merged.set(Number(candle.time), candle)
  }
  for (const candle of incoming) {
    merged.set(Number(candle.time), candle)
  }
  return [...merged.values()].sort((left, right) => Number(left.time) - Number(right.time))
}

export default function NiftyChart() {
  const { addToast, chain, chainIndex, optionChartSymbol, setOptionChartSymbol, spot } = useStore(useShallow((state) => ({
    addToast: state.addToast,
    chain: state.chain,
    chainIndex: state.chainIndex,
    optionChartSymbol: state.optionChartSymbol,
    setOptionChartSymbol: state.setOptionChartSymbol,
    spot: state.snapshot?.spot ?? null,
  })))
  const chartQuote = optionChartSymbol && chain
    ? (() => {
        const location = chainIndex[optionChartSymbol]
        const row = location ? chain.rows[location.rowIndex] : null
        if (!row) {
          return null
        }
        return location.side === 'call' ? row.call : row.put
      })()
    : null
  const chartSymbol = chartQuote?.symbol ?? null
  const chartSecurityId = chartQuote?.security_id ?? null
  const alertsEnabled = !chartQuote
  const chartLabel = chartQuote ? `NIFTY ${chartQuote.strike} ${chartQuote.option_type}` : 'NIFTY 50'
  const chartPrice = chartQuote?.ltp ?? spot
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const priceLinesRef = useRef<Map<string, IPriceLine>>(new Map())
  const announcedAlertIdsRef = useRef<Set<string>>(new Set())
  const candlesRef = useRef<CandlestickData<Time>[]>([])
  const lastBarRef = useRef<CandlestickData<Time> | null>(null)
  const nextBeforeRef = useRef<number | null>(null)
  const hasMoreHistoryRef = useRef(false)
  const loadingMoreHistoryRef = useRef(false)
  const historySessionRef = useRef(0)
  const alertsEnabledRef = useRef(alertsEnabled)
  const [timeframe, setTimeframe] = useState<(typeof TIMEFRAMES)[number]>('D')
  const [loading, setLoading] = useState(true)
  const [loadingMoreHistory, setLoadingMoreHistory] = useState(false)
  const [candleCount, setCandleCount] = useState(0)
  const [alerts, setAlerts] = useState<AlertSummary[]>([])
  const [pendingAlert, setPendingAlert] = useState<{ price: number; x: number; y: number } | null>(null)
  const [submittingAlert, setSubmittingAlert] = useState(false)
  const [alertsPanelOpen, setAlertsPanelOpen] = useState(true)

  useEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }

    const colors = getChartColors()
    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
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

    const handleClick = (param: MouseEventParams<Time>) => {
      if (!alertsEnabledRef.current) {
        setPendingAlert(null)
        return
      }
      if (!param.point) {
        setPendingAlert(null)
        return
      }
      const price = series.coordinateToPrice(param.point.y)
      if (price === null) {
        setPendingAlert(null)
        return
      }
      setPendingAlert({
        price: Number(price.toFixed(2)),
        x: param.point.x,
        y: param.point.y,
      })
    }
    chart.subscribeClick(handleClick)

    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight })
    })
    observer.observe(container)
    const priceLines = priceLinesRef.current

    return () => {
      chart.unsubscribeClick(handleClick)
      observer.disconnect()
      for (const line of priceLines.values()) {
        series.removePriceLine(line)
      }
      priceLines.clear()
      chartRef.current = null
      seriesRef.current = null
      chart.remove()
    }
  }, [])

  useEffect(() => {
    alertsEnabledRef.current = alertsEnabled
    if (!alertsEnabled) {
      setPendingAlert(null)
    }
  }, [alertsEnabled])

  useEffect(() => {
    if (!alertsEnabled) {
      setAlerts([])
      return
    }

    let cancelled = false

    const loadAlerts = async () => {
      try {
        const nextAlerts = await fetchAlerts()
        if (!cancelled) {
          setAlerts(nextAlerts.filter((alert) => alert.symbol === 'NIFTY 50'))
        }
      } catch {
        if (!cancelled) {
          setAlerts([])
        }
      }
    }

    void loadAlerts()
    const interval = window.setInterval(() => {
      void loadAlerts()
    }, 5000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [alertsEnabled])

  useEffect(() => {
    let active = true
    historySessionRef.current += 1
    const session = historySessionRef.current
    setLoading(true)
    candlesRef.current = []
    lastBarRef.current = null
    nextBeforeRef.current = null
    hasMoreHistoryRef.current = false
    loadingMoreHistoryRef.current = false
    setLoadingMoreHistory(false)

    fetchCandles({
      timeframe,
      symbol: chartSymbol,
      securityId: chartSecurityId,
    })
      .then((response) => {
        if (!active || historySessionRef.current !== session) {
          return
        }
        const candles = toChartCandles(response.candles)
        candlesRef.current = candles
        lastBarRef.current = candles.at(-1) ?? null
        nextBeforeRef.current = response.next_before ?? null
        hasMoreHistoryRef.current = response.has_more
        seriesRef.current?.setData(candles)
        chartRef.current?.timeScale().fitContent()
        setCandleCount(candles.length)
      })
      .catch((error) => {
        if (!active || historySessionRef.current !== session) {
          return
        }
        candlesRef.current = []
        lastBarRef.current = null
        nextBeforeRef.current = null
        hasMoreHistoryRef.current = false
        seriesRef.current?.setData([])
        setCandleCount(0)
        if (optionChartSymbol && error instanceof ApiError && [400, 404, 503].includes(error.status)) {
          setOptionChartSymbol(null)
          addToast('error', 'Option chart unavailable. Switched back to NIFTY 50.')
          return
        }
        addToast('error', error instanceof Error ? error.message : 'Failed to load chart history')
      })
      .finally(() => {
        if (active && historySessionRef.current === session) {
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [addToast, chartSecurityId, chartSymbol, optionChartSymbol, setOptionChartSymbol, timeframe])

  useEffect(() => {
    const chart = chartRef.current
    const series = seriesRef.current
    if (!chart || !series) {
      return
    }

    const loadMoreHistory = async (range: LogicalRange) => {
      if (
        loading
        || loadingMoreHistoryRef.current
        || !hasMoreHistoryRef.current
        || nextBeforeRef.current === null
      ) {
        return
      }

      const barsInfo = series.barsInLogicalRange(range)
      if (!barsInfo || barsInfo.barsBefore > 15) {
        return
      }

      const session = historySessionRef.current
      const before = nextBeforeRef.current
      const previousRange = chart.timeScale().getVisibleLogicalRange()
      const previousLength = candlesRef.current.length

      loadingMoreHistoryRef.current = true
      setLoadingMoreHistory(true)
      try {
        const response = await fetchCandles({
          timeframe,
          before,
          symbol: chartSymbol,
          securityId: chartSecurityId,
        })
        if (historySessionRef.current !== session) {
          return
        }

        const merged = mergeCandles(toChartCandles(response.candles), candlesRef.current)
        const addedCount = merged.length - previousLength

        candlesRef.current = merged
        lastBarRef.current = merged.at(-1) ?? null
        nextBeforeRef.current = response.next_before ?? null
        hasMoreHistoryRef.current = response.has_more
        series.setData(merged)
        setCandleCount(merged.length)

        if (previousRange && addedCount > 0) {
          chart.timeScale().setVisibleLogicalRange({
            from: previousRange.from + addedCount,
            to: previousRange.to + addedCount,
          })
        }
      } catch (error) {
        if (historySessionRef.current === session) {
          hasMoreHistoryRef.current = false
          nextBeforeRef.current = null
          addToast('error', error instanceof Error ? error.message : 'Failed to load older chart history')
        }
      } finally {
        if (historySessionRef.current === session) {
          loadingMoreHistoryRef.current = false
          setLoadingMoreHistory(false)
        }
      }
    }

    const handleRangeChange = (range: LogicalRange | null) => {
      if (!range) {
        return
      }
      void loadMoreHistory(range)
    }

    chart.timeScale().subscribeVisibleLogicalRangeChange(handleRangeChange)
    return () => {
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleRangeChange)
    }
  }, [addToast, chartSecurityId, chartSymbol, loading, timeframe])

  useEffect(() => {
    if (!chartPrice || chartPrice <= 0 || !seriesRef.current || !lastBarRef.current) {
      return
    }

    const lastBar = lastBarRef.current
    const nextBoundary = Number(lastBar.time) + timeframeSeconds(timeframe)
    const now = Math.floor(Date.now() / 1000)

    if (now >= nextBoundary) {
      const nextBar: CandlestickData<Time> = {
        time: nextBoundary as Time,
        open: lastBar.close,
        high: chartPrice,
        low: chartPrice,
        close: chartPrice,
      }
      lastBarRef.current = nextBar
      candlesRef.current = [...candlesRef.current, nextBar]
      setCandleCount(candlesRef.current.length)
      seriesRef.current.update(nextBar)
      return
    }

    const nextBar: CandlestickData<Time> = {
      ...lastBar,
      high: Math.max(lastBar.high, chartPrice),
      low: Math.min(lastBar.low, chartPrice),
      close: chartPrice,
    }

    if (
      nextBar.close === lastBar.close
      && nextBar.high === lastBar.high
      && nextBar.low === lastBar.low
    ) {
      return
    }

    lastBarRef.current = nextBar
    candlesRef.current = candlesRef.current.map((bar, index, source) => (
      index === source.length - 1 ? nextBar : bar
    ))
    seriesRef.current.update(nextBar)
  }, [chartPrice, timeframe])

  useEffect(() => {
    const series = seriesRef.current
    if (!series) {
      return
    }

    for (const line of priceLinesRef.current.values()) {
      series.removePriceLine(line)
    }
    priceLinesRef.current.clear()

    for (const alert of alerts) {
      const line = series.createPriceLine({
        price: alert.target_price,
        color: alert.status === 'TRIGGERED' ? '#16a34a' : '#f59e0b',
        lineWidth: 1,
        lineStyle: alert.status === 'TRIGGERED' ? LineStyle.Solid : LineStyle.Dashed,
        axisLabelVisible: true,
        title: `${alert.direction === 'ABOVE' ? '↑' : '↓'} Alert`,
      })
      priceLinesRef.current.set(alert.id, line)
    }
  }, [alerts])

  useEffect(() => {
    const triggered = alerts.filter((alert) => alert.status === 'TRIGGERED')
    for (const alert of triggered) {
      if (announcedAlertIdsRef.current.has(alert.id)) {
        continue
      }
      announcedAlertIdsRef.current.add(alert.id)
      addToast(
        'info',
        `Alert triggered: ${alert.symbol} ${alert.direction === 'ABOVE' ? 'above' : 'below'} ${alert.target_price.toFixed(2)}`,
      )
    }
  }, [addToast, alerts])

  const activeAlerts = alerts.filter((alert) => alert.status === 'ACTIVE')
  const triggeredAlerts = alerts.filter((alert) => alert.status === 'TRIGGERED')
  const alertPopupStyle = pendingAlert && containerRef.current
    ? {
        left: Math.min(Math.max(pendingAlert.x + 12, 12), Math.max(containerRef.current.clientWidth - 220, 12)),
        top: Math.min(Math.max(pendingAlert.y + 12, 12), Math.max(containerRef.current.clientHeight - 96, 12)),
      }
    : undefined

  return (
    <div className="relative flex h-full flex-col bg-bg-primary">
      <div className="flex items-center gap-1 border-b border-border-secondary px-3 py-1">
        <span className="mr-2 text-[11px] text-text-muted">{chartLabel}</span>
        {chartQuote && (
          <div className="mr-2 flex items-center gap-1">
            <span className="text-[11px] text-brand">{chartQuote.expiry}</span>
            <button
              onClick={() => setOptionChartSymbol(null)}
              className="text-[10px] text-text-muted hover:text-text-primary"
            >
              × Back
            </button>
          </div>
        )}
        {chartPrice ? (
          <span className="mr-3 text-[11px] text-text-secondary">
            {chartQuote ? 'LTP' : 'Spot'} {chartPrice.toFixed(2)}
          </span>
        ) : null}
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
                  ? 'rounded-sm bg-brand text-bg-primary'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2 text-[11px] text-text-muted">
          {loadingMoreHistory ? <span>Loading older…</span> : null}
          {alertsEnabled ? (
            <>
              <Bell size={12} className="text-signal" />
              <span>{activeAlerts.length} active</span>
              {triggeredAlerts.length ? <span>{triggeredAlerts.length} triggered</span> : null}
            </>
          ) : (
            <span>Live option chart</span>
          )}
        </div>
      </div>

      <div ref={containerRef} className="relative flex-1 min-h-0">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-bg-primary/80">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-signal border-t-transparent" />
          </div>
        )}
        {candleCount === 0 && !loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-text-muted">
            <span className="text-sm">{chartQuote ? 'No candle history for this option' : 'Market closed'}</span>
            <span className="mt-1 text-xs">
              {chartQuote ? chartQuote.symbol : 'NSE trading hours: 9:15 AM – 3:30 PM IST'}
            </span>
          </div>
        )}
        {alertsEnabled && pendingAlert && alertPopupStyle ? (
          <div
            className="absolute z-20 w-52 rounded-md border border-border-primary bg-bg-secondary/95 p-3 shadow-xl backdrop-blur"
            style={alertPopupStyle}
          >
            <div className="mb-1 flex items-center justify-between">
              <div className="text-[11px] font-medium text-text-primary">Create alert</div>
              <button onClick={() => setPendingAlert(null)} className="text-text-muted hover:text-text-primary">
                <X size={12} />
              </button>
            </div>
            <div className="text-[11px] text-text-muted">NIFTY 50 spot</div>
            <div className="mt-1 text-sm font-semibold tabular-nums text-text-primary">
              {pendingAlert.price.toFixed(2)}
            </div>
            <button
              onClick={async () => {
                setSubmittingAlert(true)
                try {
                  const created = await createAlert({ symbol: 'NIFTY 50', target_price: pendingAlert.price })
                  setAlerts((current) => [...current.filter((item) => item.id !== created.id), created])
                  addToast('success', `Alert added at ${created.target_price.toFixed(2)}`)
                  setPendingAlert(null)
                } catch (error) {
                  addToast('error', error instanceof Error ? error.message : 'Failed to create alert')
                } finally {
                  setSubmittingAlert(false)
                }
              }}
              disabled={submittingAlert}
              className="mt-3 w-full rounded-sm bg-signal px-3 py-2 text-[11px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {submittingAlert ? 'Adding…' : 'Add alert'}
            </button>
          </div>
        ) : null}

        {alertsPanelOpen ? <div className="absolute right-3 top-3 z-10 w-64 rounded-md border border-border-primary bg-bg-secondary/90 p-3 shadow-lg backdrop-blur">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bell size={14} className="text-signal" />
              <span className="text-[11px] font-medium text-text-primary">Chart alerts</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-text-muted">{alertsEnabled ? 'Spot' : 'Option'}</span>
              <button
                onClick={() => setAlertsPanelOpen(false)}
                className="text-text-muted hover:text-text-primary transition-colors"
              >
                <X size={12} />
              </button>
            </div>
          </div>
          <div className="mt-2 space-y-2">
            {!alertsEnabled ? (
              <div className="text-[11px] leading-4 text-text-muted">
                Option candles are live, but persisted alerts remain scoped to the NIFTY spot chart.
              </div>
            ) : alerts.length === 0 ? (
              <div className="text-[11px] leading-4 text-text-muted">
                Click any price on the chart to place an alert line, similar to TradingView.
              </div>
            ) : (
              alerts.map((alert) => (
                <div key={alert.id} className="rounded-sm border border-border-secondary bg-bg-primary/80 px-2 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-text-muted">{alert.direction}</div>
                      <div className="text-sm font-medium tabular-nums text-text-primary">{alert.target_price.toFixed(2)}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                          alert.status === 'TRIGGERED'
                            ? 'bg-profit/15 text-profit'
                            : 'bg-signal/15 text-signal'
                        }`}
                      >
                        {alert.status}
                      </span>
                      <button
                        onClick={async () => {
                          try {
                            await deleteAlert(alert.id)
                            setAlerts((current) => current.filter((item) => item.id !== alert.id))
                          } catch (error) {
                            addToast('error', error instanceof Error ? error.message : 'Failed to remove alert')
                          }
                        }}
                        className="text-text-muted hover:text-text-primary"
                        title="Remove alert"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  </div>
                  {alert.last_price != null ? (
                    <div className="mt-1 text-[10px] text-text-muted">
                      Last seen {alert.last_price.toFixed(2)}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div> : (
          <button
            onClick={() => setAlertsPanelOpen(true)}
            className="absolute right-3 top-3 z-10 flex h-7 w-7 items-center justify-center rounded-md border border-border-primary bg-bg-secondary/90 text-text-muted hover:text-text-primary shadow-lg backdrop-blur transition-colors"
            title="Show alerts"
          >
            <Bell size={14} />
          </button>
        )}
      </div>
    </div>
  )
}
