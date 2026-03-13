import { useEffect, useEffectEvent, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from 'react'
import { Bell, Plus, Trash2, X } from 'lucide-react'
import { createChart } from 'lightweight-charts'
import type { CandlestickData, IChartApi, ISeriesApi, LogicalRange, MouseEventParams, Time } from 'lightweight-charts'
import { useShallow } from 'zustand/react/shallow'

import {
  ApiError,
  createAlert,
  deleteAlert,
  fetchCandles,
  updateAlert,
  type AlertSummary,
  type Candle,
} from '../lib/api'
import { useStore } from '../store/useStore'

const TIMEFRAMES = ['1m', '5m', '15m', '1h', 'D', 'W', 'M'] as const
const IST_OFFSET_SECONDS = 5.5 * 60 * 60
const ALERT_MODAL_WIDTH = 184
const ALERT_MODAL_MAX_HEIGHT = 138
const ALERT_MODAL_RIGHT = 14
const AXIS_ADD_BUTTON_RIGHT = 74
const DRAG_THRESHOLD_PX = 5

type HoveredCandleStats = {
  time: number
  open: number
  high: number
  low: number
  close: number
  change: number | null
  changePct: number | null
}

type ChartAnchor = {
  price: number
  y: number
}

type AlertModalState =
  | { mode: 'create'; price: number; y: number }
  | { mode: 'edit'; alertId: string; price: number; y: number }

type AlertMutation =
  | { kind: 'create' }
  | { kind: 'update'; alertId: string }
  | { kind: 'delete'; alertId: string }
  | null

type DragState = {
  alert: AlertSummary
  startClientY: number
  startPrice: number
  currentPrice: number
  moved: boolean
}

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

function nextBarBoundary(time: number, timeframe: (typeof TIMEFRAMES)[number]) {
  const map = {
    '1m': 60,
    '5m': 300,
    '15m': 900,
    '1h': 3600,
    D: 86400,
    W: 7 * 86400,
  } as const
  if (timeframe !== 'M') {
    return time + map[timeframe]
  }

  const istDate = new Date((time + IST_OFFSET_SECONDS) * 1000)
  const nextMonthStart = Date.UTC(istDate.getUTCFullYear(), istDate.getUTCMonth() + 1, 1)
  return Math.floor(nextMonthStart / 1000) - IST_OFFSET_SECONDS
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

function findCandleIndexByTime(candles: CandlestickData<Time>[], time: number) {
  let left = 0
  let right = candles.length - 1
  while (left <= right) {
    const middle = Math.floor((left + right) / 2)
    const value = Number(candles[middle].time)
    if (value === time) {
      return middle
    }
    if (value < time) {
      left = middle + 1
    } else {
      right = middle - 1
    }
  }
  return -1
}

function toHoveredCandleStats(candles: CandlestickData<Time>[], index: number): HoveredCandleStats | null {
  const candle = candles[index]
  if (!candle) {
    return null
  }

  const previousClose = index > 0 ? candles[index - 1]?.close ?? null : null
  const change = previousClose === null ? null : candle.close - previousClose
  const changePct = previousClose && previousClose !== 0 ? (change! / previousClose) * 100 : null

  return {
    time: Number(candle.time),
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
    change,
    changePct,
  }
}

function formatPrice(value: number) {
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatSignedPrice(value: number) {
  return `${value >= 0 ? '+' : '-'}${formatPrice(Math.abs(value))}`
}

function formatSignedPercent(value: number) {
  return `${value >= 0 ? '+' : '-'}${Math.abs(value).toFixed(2)}%`
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function roundAlertPrice(value: number) {
  return Number(value.toFixed(2))
}

function toAlertAnchor(series: ISeriesApi<'Candlestick'>, y: number): ChartAnchor | null {
  const price = series.coordinateToPrice(y)
  if (price === null || !Number.isFinite(price)) {
    return null
  }
  return {
    price: roundAlertPrice(price),
    y,
  }
}

function isTextInputTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false
  }
  return target.tagName === 'INPUT'
    || target.tagName === 'TEXTAREA'
    || target.tagName === 'SELECT'
    || target.isContentEditable
}

export default function NiftyChart() {
  const {
    addToast,
    alerts,
    chain,
    chainIndex,
    optionChartSymbol,
    removeAlert,
    setOptionChartSymbol,
    spot,
    upsertAlert,
  } = useStore(useShallow((state) => ({
    addToast: state.addToast,
    alerts: state.alerts,
    chain: state.chain,
    chainIndex: state.chainIndex,
    optionChartSymbol: state.optionChartSymbol,
    removeAlert: state.removeAlert,
    setOptionChartSymbol: state.setOptionChartSymbol,
    spot: state.snapshot?.spot ?? null,
    upsertAlert: state.upsertAlert,
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
  const chartLabel = chartQuote ? `NIFTY ${chartQuote.strike} ${chartQuote.option_type}` : 'NIFTY 50'
  const chartPrice = chartQuote?.ltp ?? spot
  const alertSymbol = chartQuote?.symbol ?? 'NIFTY 50'
  const alertInstrumentLabel = chartQuote ? `${chartQuote.strike} ${chartQuote.option_type} · ${chartQuote.expiry}` : 'NIFTY 50 spot'
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const candlesRef = useRef<CandlestickData<Time>[]>([])
  const lastBarRef = useRef<CandlestickData<Time> | null>(null)
  const nextBeforeRef = useRef<number | null>(null)
  const hasMoreHistoryRef = useRef(false)
  const loadingMoreHistoryRef = useRef(false)
  const historySessionRef = useRef(0)
  const hoveredCandleTimeRef = useRef<number | null>(null)
  const dragStateRef = useRef<DragState | null>(null)
  const dragCleanupRef = useRef<(() => void) | null>(null)
  const [timeframe, setTimeframe] = useState<(typeof TIMEFRAMES)[number]>('D')
  const [loading, setLoading] = useState(true)
  const [loadingMoreHistory, setLoadingMoreHistory] = useState(false)
  const [candleCount, setCandleCount] = useState(0)
  const [hoveredAlertAnchor, setHoveredAlertAnchor] = useState<ChartAnchor | null>(null)
  const [selectedAlertAnchor, setSelectedAlertAnchor] = useState<ChartAnchor | null>(null)
  const [alertModal, setAlertModal] = useState<AlertModalState | null>(null)
  const [alertDraftPrice, setAlertDraftPrice] = useState('')
  const [alertMutation, setAlertMutation] = useState<AlertMutation>(null)
  const [dragPreview, setDragPreview] = useState<{ alertId: string; price: number } | null>(null)
  const [alertsPanelOpen, setAlertsPanelOpen] = useState(false)
  const [hoveredCandleStats, setHoveredCandleStats] = useState<HoveredCandleStats | null>(null)
  const [, setOverlayRevision] = useState(0)

  const syncHoveredCandleStats = useEffectEvent((time: number | null = hoveredCandleTimeRef.current) => {
    const candles = candlesRef.current
    if (candles.length === 0) {
      setHoveredCandleStats(null)
      return
    }

    const fallback = toHoveredCandleStats(candles, candles.length - 1)
    if (time === null) {
      setHoveredCandleStats(fallback)
      return
    }

    const index = findCandleIndexByTime(candles, time)
    if (index === -1) {
      hoveredCandleTimeRef.current = null
      setHoveredCandleStats(fallback)
      return
    }

    setHoveredCandleStats(toHoveredCandleStats(candles, index))
  })

  const closeAlertModal = () => {
    setAlertModal(null)
    setAlertDraftPrice('')
  }

  const openCreateAlertModal = (anchor: ChartAnchor) => {
    setAlertModal({ mode: 'create', price: anchor.price, y: anchor.y })
    setAlertDraftPrice(anchor.price.toFixed(2))
    setSelectedAlertAnchor(anchor)
  }

  const openEditAlertModal = (alert: AlertSummary, price: number = alert.target_price) => {
    const series = seriesRef.current
    const fallbackY = containerRef.current ? containerRef.current.clientHeight / 2 : 0
    const nextY = series ? series.priceToCoordinate(price) ?? fallbackY : fallbackY
    const anchor = { price: roundAlertPrice(price), y: nextY }
    setAlertModal({ mode: 'edit', alertId: alert.id, price: anchor.price, y: anchor.y })
    setAlertDraftPrice(anchor.price.toFixed(2))
    setSelectedAlertAnchor(anchor)
  }

  const syncLiveChartPrice = useEffectEvent(() => {
    const price = chartQuote?.ltp ?? spot
    if (!price || price <= 0 || !seriesRef.current || !lastBarRef.current) {
      return
    }

    const lastBar = lastBarRef.current
    const nextBoundary = nextBarBoundary(Number(lastBar.time), timeframe)
    const now = Math.floor(Date.now() / 1000)

    if (now >= nextBoundary) {
      const nextBar: CandlestickData<Time> = {
        time: nextBoundary as Time,
        open: lastBar.close,
        high: price,
        low: price,
        close: price,
      }
      lastBarRef.current = nextBar
      candlesRef.current = [...candlesRef.current, nextBar]
      setCandleCount(candlesRef.current.length)
      seriesRef.current.update(nextBar)
      syncHoveredCandleStats()
      setOverlayRevision((value) => value + 1)
      return
    }

    const nextBar: CandlestickData<Time> = {
      ...lastBar,
      high: Math.max(lastBar.high, price),
      low: Math.min(lastBar.low, price),
      close: price,
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
    syncHoveredCandleStats()
    setOverlayRevision((value) => value + 1)
  })

  const submitAlertModal = async () => {
    if (!alertModal) {
      return
    }

    const targetPrice = Number.parseFloat(alertDraftPrice)
    if (!Number.isFinite(targetPrice) || targetPrice <= 0) {
      addToast('error', 'Enter a valid alert price')
      return
    }

    const roundedTargetPrice = roundAlertPrice(targetPrice)

    if (alertModal.mode === 'create') {
      setAlertMutation({ kind: 'create' })
      try {
        const created = await createAlert({ symbol: alertSymbol, target_price: roundedTargetPrice })
        upsertAlert(created)
        addToast('success', `Alert added at ${created.target_price.toFixed(2)}`)
        closeAlertModal()
      } catch (error) {
        addToast('error', error instanceof Error ? error.message : 'Failed to create alert')
      } finally {
        setAlertMutation(null)
      }
      return
    }

    setAlertMutation({ kind: 'update', alertId: alertModal.alertId })
    try {
      const updated = await updateAlert(alertModal.alertId, { target_price: roundedTargetPrice })
      upsertAlert(updated)
      setDragPreview((current) => (current?.alertId === updated.id ? null : current))
      addToast('success', `Alert updated to ${updated.target_price.toFixed(2)}`)
      closeAlertModal()
    } catch (error) {
      addToast('error', error instanceof Error ? error.message : 'Failed to update alert')
    } finally {
      setAlertMutation(null)
    }
  }

  const handleDeleteAlert = async (alertId: string) => {
    setAlertMutation({ kind: 'delete', alertId })
    try {
      await deleteAlert(alertId)
      removeAlert(alertId)
      setDragPreview((current) => (current?.alertId === alertId ? null : current))
      if (alertModal?.mode === 'edit' && alertModal.alertId === alertId) {
        closeAlertModal()
      }
      addToast('success', 'Alert deleted')
    } catch (error) {
      addToast('error', error instanceof Error ? error.message : 'Failed to remove alert')
    } finally {
      setAlertMutation(null)
    }
  }

  const startAlertLineInteraction = (event: ReactPointerEvent<HTMLDivElement>, alert: AlertSummary) => {
    event.preventDefault()
    event.stopPropagation()

    if (alertMutation) {
      return
    }

    const initialPrice = dragPreview?.alertId === alert.id ? dragPreview.price : alert.target_price
    dragStateRef.current = {
      alert,
      startClientY: event.clientY,
      startPrice: initialPrice,
      currentPrice: initialPrice,
      moved: false,
    }

    const cleanup = () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
      window.removeEventListener('pointercancel', handlePointerCancel)
      if (dragCleanupRef.current === cleanup) {
        dragCleanupRef.current = null
      }
    }

    const finishDrag = async (cancelled: boolean) => {
      cleanup()
      document.body.style.userSelect = ''
      const state = dragStateRef.current
      dragStateRef.current = null
      if (!state) {
        return
      }

      if (cancelled) {
        setDragPreview(null)
        return
      }

      if (!state.moved) {
        openEditAlertModal(state.alert, state.startPrice)
        return
      }

      setDragPreview(null)
      if (state.currentPrice === state.alert.target_price) {
        return
      }

      setAlertMutation({ kind: 'update', alertId: state.alert.id })
      try {
        const updated = await updateAlert(state.alert.id, { target_price: state.currentPrice })
        upsertAlert(updated)
        addToast('success', `Alert moved to ${updated.target_price.toFixed(2)}`)
      } catch (error) {
        addToast('error', error instanceof Error ? error.message : 'Failed to move alert')
      } finally {
        setAlertMutation(null)
      }
    }

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const container = containerRef.current
      const series = seriesRef.current
      const state = dragStateRef.current
      if (!container || !series || !state) {
        return
      }

      const rect = container.getBoundingClientRect()
      const nextAnchor = toAlertAnchor(series, clamp(moveEvent.clientY - rect.top, 0, rect.height))
      if (!nextAnchor) {
        return
      }

      if (!state.moved && Math.abs(moveEvent.clientY - state.startClientY) > DRAG_THRESHOLD_PX) {
        state.moved = true
        if (alertModal?.mode === 'edit' && alertModal.alertId === state.alert.id) {
          closeAlertModal()
        }
      }

      if (!state.moved) {
        return
      }

      state.currentPrice = nextAnchor.price
      setDragPreview({ alertId: state.alert.id, price: nextAnchor.price })
      setOverlayRevision((value) => value + 1)
    }

    const handlePointerUp = () => {
      void finishDrag(false)
    }

    const handlePointerCancel = () => {
      void finishDrag(true)
    }

    dragCleanupRef.current = cleanup
    document.body.style.userSelect = 'none'
    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp, { once: true })
    window.addEventListener('pointercancel', handlePointerCancel, { once: true })
  }

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
      if (!param.point) {
        return
      }
      const nextAnchor = toAlertAnchor(series, param.point.y)
      setSelectedAlertAnchor(nextAnchor)
      container.focus()
    }
    chart.subscribeClick(handleClick)

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      setHoveredAlertAnchor(param.point ? toAlertAnchor(series, param.point.y) : null)

      const candle = param.seriesData.get(series) as CandlestickData<Time> | undefined
      if (!param.point || !param.time || !candle) {
        hoveredCandleTimeRef.current = null
        syncHoveredCandleStats(null)
        return
      }

      hoveredCandleTimeRef.current = Number(param.time)
      syncHoveredCandleStats(Number(param.time))
    }
    chart.subscribeCrosshairMove(handleCrosshairMove)

    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight })
      setOverlayRevision((value) => value + 1)
    })
    observer.observe(container)

    return () => {
      chart.unsubscribeClick(handleClick)
      chart.unsubscribeCrosshairMove(handleCrosshairMove)
      observer.disconnect()
      chartRef.current = null
      seriesRef.current = null
      chart.remove()
    }
  }, [])

  useEffect(() => {
    dragCleanupRef.current?.()
    dragCleanupRef.current = null
    dragStateRef.current = null
    document.body.style.userSelect = ''
    setHoveredAlertAnchor(null)
    setSelectedAlertAnchor(null)
    setAlertModal(null)
    setAlertDraftPrice('')
    setDragPreview(null)
    setAlertMutation(null)
  }, [alertSymbol])

  useEffect(() => {
    return () => {
      dragCleanupRef.current?.()
      dragCleanupRef.current = null
      dragStateRef.current = null
      document.body.style.userSelect = ''
    }
  }, [])

  useEffect(() => {
    let active = true
    historySessionRef.current += 1
    const session = historySessionRef.current
    setLoading(true)
    hoveredCandleTimeRef.current = null
    setHoveredCandleStats(null)
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
        syncHoveredCandleStats(null)
        syncLiveChartPrice()
        setOverlayRevision((value) => value + 1)
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
        setHoveredCandleStats(null)
        setOverlayRevision((value) => value + 1)
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
        syncHoveredCandleStats()
        setOverlayRevision((value) => value + 1)

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
      setOverlayRevision((value) => value + 1)
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
    syncLiveChartPrice()
  }, [candleCount, chartPrice, chartSymbol, timeframe])

  useEffect(() => {
    if (alertModal?.mode === 'edit' && !alerts.some((alert) => alert.id === alertModal.alertId)) {
      setAlertModal(null)
      setAlertDraftPrice('')
    }
  }, [alertModal, alerts])

  const chartAlerts = alerts.filter((alert) => alert.symbol === alertSymbol)
  const activeAlerts = chartAlerts.filter((alert) => alert.status === 'ACTIVE')
  const triggeredAlerts = chartAlerts.filter((alert) => alert.status === 'TRIGGERED')
  const editingAlert = alertModal?.mode === 'edit'
    ? chartAlerts.find((alert) => alert.id === alertModal.alertId) ?? null
    : null
  const editingAlertId = alertModal?.mode === 'edit' ? alertModal.alertId : null
  const isCreatingAlert = alertMutation?.kind === 'create'
  const isSavingAlert = alertMutation?.kind === 'update' && alertMutation.alertId === editingAlertId
  const isDeletingAlert = alertMutation?.kind === 'delete' && alertMutation.alertId === editingAlertId
  const hoverChangeTone = hoveredCandleStats?.change == null
    ? 'text-text-secondary'
    : hoveredCandleStats.change >= 0
      ? 'text-profit'
      : 'text-loss'
  const shortcutAnchor = selectedAlertAnchor ?? hoveredAlertAnchor
  const containerHeight = containerRef.current?.clientHeight ?? 0
  const modalCoordinate = alertModal
    ? alertModal.mode === 'edit' && editingAlert && seriesRef.current
      ? seriesRef.current.priceToCoordinate(dragPreview?.alertId === editingAlert.id ? dragPreview.price : editingAlert.target_price) ?? alertModal.y
      : alertModal.y
    : null
  const alertModalStyle = alertModal && containerRef.current && modalCoordinate !== null
    ? {
        right: ALERT_MODAL_RIGHT,
        top: clamp(
          modalCoordinate - 46,
          12,
          Math.max(containerRef.current.clientHeight - ALERT_MODAL_MAX_HEIGHT, 12),
        ),
        width: ALERT_MODAL_WIDTH,
      }
    : undefined
  const overlayAlerts = seriesRef.current && containerHeight > 0
    ? chartAlerts.flatMap((alert) => {
        const displayPrice = dragPreview?.alertId === alert.id ? dragPreview.price : alert.target_price
        const coordinate = seriesRef.current?.priceToCoordinate(displayPrice)
        if (coordinate === null || coordinate === undefined || !Number.isFinite(coordinate)) {
          return []
        }
        if (coordinate < -24 || coordinate > containerHeight + 24) {
          return []
        }
        return [{ alert, price: displayPrice, y: clamp(coordinate, 0, containerHeight) }]
      })
    : []

  const handleChartPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.target instanceof HTMLElement && event.target.closest('[data-alert-interactive="true"]')) {
      return
    }
    event.currentTarget.focus()
  }

  const handleChartKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape' && alertModal) {
      closeAlertModal()
      event.preventDefault()
      return
    }

    if (event.metaKey || event.ctrlKey || event.altKey || isTextInputTarget(event.target)) {
      return
    }

    if ((event.key === 'a' || event.key === 'A') && shortcutAnchor && !alertModal) {
      openCreateAlertModal(shortcutAnchor)
      event.preventDefault()
    }
  }

  return (
    <div className="relative flex h-full flex-col bg-bg-primary">
      <div className={`flex flex-wrap items-center gap-x-2 gap-y-1 border-b px-3 py-1 ${chartQuote ? 'border-brand/30 bg-brand/5' : 'border-border-secondary'}`}>
        <span className={`mr-2 text-[11px] ${chartQuote ? 'font-medium text-brand' : 'text-text-muted'}`}>{chartLabel}</span>
        {chartQuote && (
          <div className="mr-2 flex items-center gap-1">
            <span className="text-[10px] text-text-muted">{chartQuote.expiry}</span>
            <button
              onClick={() => setOptionChartSymbol(null)}
              className="ml-1 rounded-sm border border-border-primary bg-bg-secondary px-1.5 py-0.5 text-[10px] text-text-muted transition-colors hover:border-text-muted hover:text-text-primary"
            >
              Back to NIFTY
            </button>
          </div>
        )}
        {hoveredCandleStats ? (
          <div className="mr-3 flex min-w-0 items-center gap-2 overflow-hidden whitespace-nowrap text-[11px] tabular-nums text-text-secondary">
            <span>O {formatPrice(hoveredCandleStats.open)}</span>
            <span>H {formatPrice(hoveredCandleStats.high)}</span>
            <span>L {formatPrice(hoveredCandleStats.low)}</span>
            <span>C {formatPrice(hoveredCandleStats.close)}</span>
            {hoveredCandleStats.change != null && hoveredCandleStats.changePct != null ? (
              <span className={hoverChangeTone}>
                {formatSignedPrice(hoveredCandleStats.change)} ({formatSignedPercent(hoveredCandleStats.changePct)})
              </span>
            ) : null}
          </div>
        ) : chartPrice ? (
          <span className="mr-3 text-[11px] tabular-nums text-text-secondary">
            {chartQuote ? 'LTP' : 'Spot'} ₹{chartPrice.toFixed(2)}
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
          <button
            onClick={() => setAlertsPanelOpen((open) => !open)}
            className={`flex items-center gap-2 rounded-sm border px-2 py-1 transition-colors ${
              alertsPanelOpen
                ? 'border-signal/60 bg-signal/10 text-text-primary'
                : 'border-border-primary text-text-muted hover:text-text-primary'
            }`}
            title={alertsPanelOpen ? 'Hide alerts' : 'Show alerts'}
          >
            <Bell size={12} className="text-signal" />
            <span>{activeAlerts.length} active</span>
            {triggeredAlerts.length ? <span>{triggeredAlerts.length} triggered</span> : null}
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        className="relative flex-1 min-h-0 outline-none"
        tabIndex={0}
        onPointerDown={handleChartPointerDown}
        onKeyDown={handleChartKeyDown}
      >
        {loading && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-bg-primary/80">
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

        <div className="pointer-events-none absolute inset-0 z-10">
          {overlayAlerts.map(({ alert, price, y }) => {
            const triggered = alert.status === 'TRIGGERED'
            return (
              <div key={alert.id} className="absolute inset-x-0" style={{ top: y }}>
                <div
                  className="absolute inset-x-0 top-0 -translate-y-1/2 border-t"
                  style={{
                    borderColor: triggered ? '#16a34a' : '#f59e0b',
                    borderTopStyle: triggered ? 'solid' : 'dashed',
                    opacity: dragPreview?.alertId === alert.id ? 1 : 0.85,
                  }}
                />
                <div
                  data-alert-interactive="true"
                  className={`pointer-events-auto absolute inset-x-0 top-0 h-5 -translate-y-1/2 ${
                    alertMutation ? 'cursor-wait' : 'cursor-grab active:cursor-grabbing'
                  }`}
                  onPointerDown={(event) => startAlertLineInteraction(event, alert)}
                  title="Drag to move alert. Click to edit."
                />
                <div className="pointer-events-none absolute right-2 top-0 -translate-y-1/2">
                  <div className="flex items-center overflow-hidden rounded-sm border border-black/15 bg-bg-primary/92 shadow-[0_4px_14px_rgba(0,0,0,0.18)]">
                    <span className={`px-2 py-0.5 text-[10px] font-medium ${triggered ? 'bg-profit text-bg-primary' : 'bg-[#f59e0b] text-[#1b1b1b]'}`}>
                      {alert.direction === 'ABOVE' ? '↑ Alert' : '↓ Alert'}
                    </span>
                    <span className="border-l border-black/10 px-2 py-0.5 text-[10px] tabular-nums text-text-primary">
                      {formatPrice(price)}
                    </span>
                  </div>
                </div>
              </div>
            )
          })}

          {hoveredAlertAnchor && !alertModal ? (
            <div
              className="absolute z-20"
              style={{ right: AXIS_ADD_BUTTON_RIGHT, top: clamp(hoveredAlertAnchor.y, 0, containerHeight || 0) }}
            >
              <button
                data-alert-interactive="true"
                onClick={(event) => {
                  event.stopPropagation()
                  openCreateAlertModal(hoveredAlertAnchor)
                }}
                className="pointer-events-auto flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full border border-border-primary/80 bg-bg-secondary/88 text-text-muted shadow-sm backdrop-blur transition-colors hover:border-signal/60 hover:text-signal"
                title="Create alert (A)"
              >
                <Plus size={10} />
              </button>
            </div>
          ) : null}
        </div>

        {alertModal && alertModalStyle ? (
          <div
            data-alert-interactive="true"
            className="absolute z-20 rounded-md border border-border-primary/90 bg-bg-secondary/96 px-3 py-2.5 shadow-xl backdrop-blur"
            style={alertModalStyle}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-[11px] font-medium text-text-primary">
                  {alertModal.mode === 'edit' ? 'Edit alert' : 'Create alert'}
                </div>
                <div className="text-[10px] text-text-muted">{alertInstrumentLabel}</div>
              </div>
              <button onClick={() => closeAlertModal()} className="text-text-muted transition-colors hover:text-text-primary">
                <X size={12} />
              </button>
            </div>

            <label className="mt-2 block">
              <span className="mb-1 block text-[10px] uppercase tracking-wide text-text-muted">Trigger price</span>
              <input
                data-alert-interactive="true"
                type="number"
                inputMode="decimal"
                min="0"
                step="0.05"
                value={alertDraftPrice}
                onChange={(event) => setAlertDraftPrice(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    void submitAlertModal()
                  }
                  if (event.key === 'Escape') {
                    event.preventDefault()
                    closeAlertModal()
                  }
                }}
                className="w-full rounded-sm border border-border-primary bg-bg-primary/80 px-2 py-1.5 text-sm tabular-nums text-text-primary outline-none transition-colors focus:border-signal/60"
              />
            </label>

            <div className="mt-2 flex items-center gap-1.5">
              <button
                onClick={() => void submitAlertModal()}
                disabled={Boolean(alertMutation)}
                className="flex-1 rounded-sm bg-signal px-3 py-1.5 text-[11px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {alertModal.mode === 'edit'
                  ? isSavingAlert ? 'Saving…' : 'Save'
                  : isCreatingAlert ? 'Adding…' : 'Add alert'}
              </button>
              {alertModal.mode === 'edit' ? (
                <button
                  onClick={() => void handleDeleteAlert(alertModal.alertId)}
                  disabled={Boolean(alertMutation)}
                  className="flex items-center gap-1 rounded-sm border border-loss/35 px-2.5 py-1.5 text-[11px] font-medium text-loss transition-colors hover:border-loss/60 hover:bg-loss/8 disabled:opacity-50"
                  title="Delete alert"
                >
                  <Trash2 size={11} />
                  <span>{isDeletingAlert ? 'Deleting…' : 'Delete'}</span>
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        {alertsPanelOpen ? (
          <div data-alert-interactive="true" className="absolute right-3 top-3 z-20 w-64 rounded-md border border-border-primary bg-bg-secondary/90 p-3 shadow-lg backdrop-blur">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bell size={14} className="text-signal" />
                <span className="text-[11px] font-medium text-text-primary">Chart alerts</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-text-muted">{chartQuote ? 'Option' : 'Spot'}</span>
                <button
                  onClick={() => setAlertsPanelOpen(false)}
                  className="text-text-muted transition-colors hover:text-text-primary"
                >
                  <X size={12} />
                </button>
              </div>
            </div>
            <div className="mt-2 space-y-2">
              <div className="text-[10px] text-text-muted">{alertInstrumentLabel}</div>
              {chartAlerts.length === 0 ? (
                <div className="text-[11px] leading-4 text-text-muted">
                  Use the subtle + on the price scale, or click the chart and press A to add an alert.
                </div>
              ) : (
                chartAlerts.map((alert) => (
                  <div key={alert.id} className="rounded-sm border border-border-secondary bg-bg-primary/80 px-2 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <button
                        onClick={() => openEditAlertModal(alert)}
                        className="min-w-0 text-left"
                      >
                        <div className="text-[10px] uppercase tracking-wide text-text-muted">{alert.direction}</div>
                        <div className="text-sm font-medium tabular-nums text-text-primary">{alert.target_price.toFixed(2)}</div>
                      </button>
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
                          onClick={() => void handleDeleteAlert(alert.id)}
                          className="text-text-muted hover:text-text-primary"
                          disabled={alertMutation?.kind === 'delete' && alertMutation.alertId === alert.id}
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
          </div>
        ) : null}
      </div>
    </div>
  )
}
