import { useEffect, useEffectEvent, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from 'react'
import { BarChart2, Bell, Eye, EyeOff, Pencil, Plus, Trash2, X } from 'lucide-react'
import { createChart } from 'lightweight-charts'
import type { CandlestickData, HistogramData, IChartApi, ISeriesApi, LogicalRange, MouseEventParams, Time } from 'lightweight-charts'
import { useShallow } from 'zustand/react/shallow'

import {
  ApiError,
  createAlert,
  deleteAlert,
  fetchCandles,
  updateAlert,
  type AlertSummary,
  type Candle,
  type CandleResponse,
} from '../lib/api'
import { useStore } from '../store/useStore'
import { DrawingContextMenu } from './chart/DrawingContextMenu'
import { DrawingToolbar } from './chart/DrawingToolbar'
import { IndicatorPanel } from './chart/IndicatorPanel'
import { OscillatorPane } from './chart/OscillatorPane'
import { DrawingManager } from '../lib/chart/drawing-manager'
import { IndicatorManager } from '../lib/chart/indicator-manager'
import { DEFAULT_DRAWING_STYLE, OSCILLATOR_INDICATORS } from '../lib/chart/types'
import type { DrawingType } from '../lib/chart/types'
import { computeRSI, computeMACD, computeADX } from '../lib/chart/indicators'

const TIMEFRAMES = ['1m', '5m', '15m', '1h', 'D', 'W', 'M'] as const
const IST_OFFSET_SECONDS = 5.5 * 60 * 60
const ALERT_MODAL_WIDTH = 184
const ALERT_MODAL_MAX_HEIGHT = 138
const ALERT_MODAL_RIGHT = 14
const AXIS_ADD_BUTTON_RIGHT = 74
const AXIS_ADD_BUTTON_HITBOX = 32
const AXIS_ADD_BUTTON_TOUCH_HITBOX = 46
const AXIS_ADD_BUTTON_VISUAL = 20
const AXIS_ADD_BUTTON_TOUCH_VISUAL = 24
const ALERT_LINE_HITBOX = 20
const ALERT_LINE_TOUCH_HITBOX = 32
const DRAG_THRESHOLD_PX = 5
const DRAG_THRESHOLD_TOUCH_PX = 12

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

function toVolumeData(candles: Candle[], bullColor: string, bearColor: string): HistogramData<Time>[] {
  return candles.map((candle) => ({
    time: (candle.time + IST_OFFSET_SECONDS) as Time,
    value: candle.volume,
    color: candle.close >= candle.open ? `${bullColor}55` : `${bearColor}55`,
  }))
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

  // Timestamps are already IST-shifted, so UTC fields give IST values
  const istDate = new Date(time * 1000)
  const nextMonthStart = Date.UTC(istDate.getUTCFullYear(), istDate.getUTCMonth() + 1, 1)
  return Math.floor(nextMonthStart / 1000)
}

function toChartCandles(candles: Candle[]) {
  return candles.map((candle) => ({
    time: (candle.time + IST_OFFSET_SECONDS) as Time,
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
    dayHigh,
    dayLow,
    optionChartSymbol,
    removeAlert,
    setOptionChartSymbol,
    setTimeframe,
    spot,
    timeframe,
    upsertAlert,
    drawingToolbar,
    activeTool,
    drawings,
    drawingInProgress,
    setDrawingToolbar,
    setActiveTool,
    setDrawingInProgress,
    addDrawing,
    loadDrawingsForSymbol,
    clearDrawings,
    selectedDrawingId,
    setSelectedDrawingId,
    updateDrawing,
    removeDrawing,
    indicatorPanelOpen,
    indicators,
    oscillatorPaneState,
    setIndicatorPanelOpen,
    toggleIndicator,
    setOscillatorPaneExpanded,
    overlayVisible,
    toggleOverlayVisible,
  } = useStore(useShallow((state) => ({
    addToast: state.addToast,
    alerts: state.alerts,
    chain: state.chain,
    chainIndex: state.chainIndex,
    dayHigh: state.snapshot?.day_high ?? null,
    dayLow: state.snapshot?.day_low ?? null,
    optionChartSymbol: state.optionChartSymbol,
    removeAlert: state.removeAlert,
    setOptionChartSymbol: state.setOptionChartSymbol,
    spot: state.snapshot?.spot ?? null,
    timeframe: state.chartTimeframe,
    setTimeframe: state.setChartTimeframe,
    upsertAlert: state.upsertAlert,
    drawingToolbar: state.drawingToolbar,
    activeTool: state.activeTool,
    drawings: state.drawings,
    drawingInProgress: state.drawingInProgress,
    setDrawingToolbar: state.setDrawingToolbar,
    setActiveTool: state.setActiveTool,
    setDrawingInProgress: state.setDrawingInProgress,
    addDrawing: state.addDrawing,
    loadDrawingsForSymbol: state.loadDrawingsForSymbol,
    clearDrawings: state.clearDrawings,
    selectedDrawingId: state.selectedDrawingId,
    setSelectedDrawingId: state.setSelectedDrawingId,
    updateDrawing: state.updateDrawing,
    removeDrawing: state.removeDrawing,
    indicatorPanelOpen: state.indicatorPanelOpen,
    indicators: state.indicators,
    oscillatorPaneState: state.oscillatorPaneState,
    setIndicatorPanelOpen: state.setIndicatorPanelOpen,
    toggleIndicator: state.toggleIndicator,
    setOscillatorPaneExpanded: state.setOscillatorPaneExpanded,
    overlayVisible: state.overlayVisible,
    toggleOverlayVisible: state.toggleOverlayVisible,
  })))
  /* timeframe & setTimeframe are now from the store, not local state */
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
  // Use option quote's day high/low when viewing an option chart
  const effectiveDayHigh = chartQuote?.day_high ?? dayHigh
  const effectiveDayLow = chartQuote?.day_low ?? dayLow
  const alertSymbol = chartQuote?.symbol ?? 'NIFTY 50'
  const alertInstrumentLabel = chartQuote ? `${chartQuote.strike} ${chartQuote.option_type} · ${chartQuote.expiry}` : 'NIFTY 50 spot'
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const candlesRef = useRef<CandlestickData<Time>[]>([])
  const rawCandlesRef = useRef<Candle[]>([])
  const lastBarRef = useRef<CandlestickData<Time> | null>(null)
  const nextBeforeRef = useRef<number | null>(null)
  const hasMoreHistoryRef = useRef(false)
  const loadingMoreHistoryRef = useRef(false)
  const historySessionRef = useRef(0)
  const hoveredCandleTimeRef = useRef<number | null>(null)
  const dragStateRef = useRef<DragState | null>(null)
  const dragCleanupRef = useRef<(() => void) | null>(null)
  const drawingManagerRef = useRef<DrawingManager | null>(null)
  const indicatorManagerRef = useRef<IndicatorManager | null>(null)
  const drawingDragRef = useRef<{ drawingId: string; symbol: string; startY: number; startX: number; startPrice: number; startTime: number; type: 'hline' | 'vline'; moved: boolean } | null>(null)
  const [loading, setLoading] = useState(true)
  const [candleRevision, setCandleRevision] = useState(0)
  const [visibleLogicalRange, setVisibleLogicalRange] = useState<LogicalRange | null>(null)
  const [, setLoadingMoreHistory] = useState(false)
  const [candleCount, setCandleCount] = useState(0)
  const [hoveredAlertAnchor, setHoveredAlertAnchor] = useState<ChartAnchor | null>(null)
  const [selectedAlertAnchor, setSelectedAlertAnchor] = useState<ChartAnchor | null>(null)
  const [alertModal, setAlertModal] = useState<AlertModalState | null>(null)
  const [alertDraftPrice, setAlertDraftPrice] = useState('')
  const [alertMutation, setAlertMutation] = useState<AlertMutation>(null)
  const [dragPreview, setDragPreview] = useState<{ alertId: string; price: number } | null>(null)
  const [alertsPanelOpen, setAlertsPanelOpen] = useState(false)
  const [drawingContextMenu, setDrawingContextMenu] = useState<{ drawingId: string; x: number; y: number } | null>(null)
  const [showVolume, setShowVolume] = useState(() => {
    try { return localStorage.getItem('chart:showVolume') !== 'false' } catch { return true }
  })
  const [hoveredCandleStats, setHoveredCandleStats] = useState<HoveredCandleStats | null>(null)
  const [hasCoarsePointer, setHasCoarsePointer] = useState(false)
  const [, setOverlayRevision] = useState(0)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return
    }

    const mediaQuery = window.matchMedia('(pointer: coarse)')
    const sync = () => {
      setHasCoarsePointer(mediaQuery.matches || navigator.maxTouchPoints > 0 || window.innerWidth <= 768)
    }

    sync()
    window.addEventListener('resize', sync)
    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', sync)
      return () => {
        window.removeEventListener('resize', sync)
        mediaQuery.removeEventListener('change', sync)
      }
    }

    mediaQuery.addListener(sync)
    return () => {
      window.removeEventListener('resize', sync)
      mediaQuery.removeListener(sync)
    }
  }, [])

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
    const now = Math.floor(Date.now() / 1000) + IST_OFFSET_SECONDS

    const nextBoundary = nextBarBoundary(Number(lastBar.time), timeframe)
    if (now >= nextBoundary) {
      // Create exactly one new bar at the current time boundary.
      // Note: intentionally NOT calling setCandleCount here — that would re-trigger
      // this effect, causing an infinite loop when many boundaries have been missed.
      const newBar: CandlestickData<Time> = {
        time: nextBoundary as Time,
        open: lastBar.close,
        high: price,
        low: price,
        close: price,
      }
      lastBarRef.current = newBar
      candlesRef.current = [...candlesRef.current, newBar]
      seriesRef.current.update(newBar)
      syncHoveredCandleStats()
      setOverlayRevision((value) => value + 1)
      return
    }

    // For daily candles, incorporate day high/low from the Dhan feed
    let high = Math.max(lastBar.high, price)
    let low = Math.min(lastBar.low, price)
    if (timeframe === 'D' && effectiveDayHigh && effectiveDayHigh > 0) high = Math.max(high, effectiveDayHigh)
    if (timeframe === 'D' && effectiveDayLow && effectiveDayLow > 0) low = Math.min(low, effectiveDayLow)

    const nextBar: CandlestickData<Time> = {
      ...lastBar,
      high,
      low,
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

  const handleDrawingClick = useEffectEvent((param: MouseEventParams) => {
    if (!activeTool || !param.time || !param.point) return
    const series = seriesRef.current
    if (!series) return
    const price = series.coordinateToPrice(param.point.y)
    if (price === null) return
    const time = Number(param.time)
    const symbol = chartQuote?.symbol ?? 'NIFTY 50'
    const point = { time, price: Number(price.toFixed(2)) }

    if (activeTool === 'hline' || activeTool === 'vline') {
      addDrawing(symbol, {
        id: crypto.randomUUID(), type: activeTool, points: [point],
        style: { ...DEFAULT_DRAWING_STYLE }, createdAt: Date.now(),
      })
      return
    }

    const current = drawingInProgress ?? []
    const next = [...current, point]
    const requiredPoints = activeTool === 'channel' ? 3 : 2
    if (next.length >= requiredPoints) {
      addDrawing(symbol, {
        id: crypto.randomUUID(), type: activeTool, points: next,
        style: { ...DEFAULT_DRAWING_STYLE }, createdAt: Date.now(),
      })
      setDrawingInProgress(null)
    } else {
      setDrawingInProgress(next)
    }
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

    const target = event.currentTarget
    try {
      target.setPointerCapture(event.pointerId)
    } catch {
      // Ignore pointer-capture failures on browsers that reject it during touch edge cases.
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
      try {
        if (target.hasPointerCapture?.(event.pointerId)) {
          target.releasePointerCapture(event.pointerId)
        }
      } catch {
        // Ignore stale pointer capture cleanup.
      }
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

      if (!state.moved && Math.abs(moveEvent.clientY - state.startClientY) > dragThresholdPx) {
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
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.03)', style: 1 },
        horzLines: { color: 'rgba(255,255,255,0.05)', style: 1 },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: 'rgba(255,255,255,0.15)', style: 3, width: 1, labelVisible: true, labelBackgroundColor: '#2a2a2a' },
        horzLine: { color: 'rgba(255,255,255,0.15)', style: 3, width: 1, labelVisible: true, labelBackgroundColor: '#2a2a2a' },
      },
      rightPriceScale: {
        borderColor: colors.borderPrimary,
        autoScale: true,
        scaleMargins: { top: 0.08, bottom: 0.18 },
      },
      timeScale: { borderColor: colors.borderPrimary, timeVisible: true, secondsVisible: false, rightOffset: 4 },
    })
    const series = chart.addCandlestickSeries({
      upColor: colors.bullColor,
      downColor: colors.bearColor,
      borderUpColor: colors.bullColor,
      borderDownColor: colors.bearColor,
      wickUpColor: colors.bullColor,
      wickDownColor: colors.bearColor,
    })
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    })
    chartRef.current = chart
    seriesRef.current = series
    volumeSeriesRef.current = volumeSeries
    drawingManagerRef.current = new DrawingManager(chart, series)
    indicatorManagerRef.current = new IndicatorManager(chart)

    const handleClick = (param: MouseEventParams<Time>) => {
      handleDrawingClick(param)
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
      drawingManagerRef.current?.destroy()
      drawingManagerRef.current = null
      indicatorManagerRef.current?.destroy()
      indicatorManagerRef.current = null
      chartRef.current = null
      seriesRef.current = null
      volumeSeriesRef.current = null
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
    const isIntraday = !['D', 'W', 'M'].includes(timeframe)
    chartRef.current?.applyOptions({
      watermark: {
        visible: true,
        text: chartLabel,
        fontSize: 64,
        color: 'rgba(255, 255, 255, 0.04)',
        horzAlign: 'center',
        vertAlign: 'center',
      },
    })
    chartRef.current?.timeScale().applyOptions({ timeVisible: isIntraday })
    hoveredCandleTimeRef.current = null
    setHoveredCandleStats(null)
    candlesRef.current = []
    rawCandlesRef.current = []
    lastBarRef.current = null
    nextBeforeRef.current = null
    hasMoreHistoryRef.current = false
    loadingMoreHistoryRef.current = false
    setLoadingMoreHistory(false)

    const params = { timeframe, symbol: chartSymbol, securityId: chartSecurityId }

    // Retry once on 503 — Dhan upstream errors are often transient
    const fetchWithRetry = () =>
      fetchCandles(params).catch((error) => {
        if (error instanceof ApiError && error.status === 503) {
          return new Promise<CandleResponse>((resolve) => setTimeout(resolve, 800))
            .then(() => fetchCandles(params))
        }
        throw error
      })

    fetchWithRetry()
      .then((response) => {
        if (!active || historySessionRef.current !== session) {
          return
        }
        const candles = toChartCandles(response.candles)
        candlesRef.current = candles
        rawCandlesRef.current = response.candles
        lastBarRef.current = candles.at(-1) ?? null
        nextBeforeRef.current = response.next_before ?? null
        hasMoreHistoryRef.current = response.has_more
        seriesRef.current?.setData(candles)
        const colors = getChartColors()
        volumeSeriesRef.current?.setData(toVolumeData(response.candles, colors.bullColor, colors.bearColor))
        const chart = chartRef.current
        if (chart && candles.length > 0) {
          // Use consistent bar spacing (~7px) for all data, scroll to latest
          const containerWidth = containerRef.current?.clientWidth ?? 390
          const usableWidth = Math.max(containerWidth - 60, 200)
          const barSpacing = Math.max(4, Math.min(usableWidth / Math.min(candles.length, Math.floor(usableWidth / 7)), 12))
          chart.timeScale().applyOptions({ barSpacing })
          chart.timeScale().scrollToRealTime()
        }
        setCandleCount(candles.length)
        setCandleRevision((v) => v + 1)
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
        volumeSeriesRef.current?.setData([])
        setCandleCount(0)
        setHoveredCandleStats(null)
        setOverlayRevision((value) => value + 1)
        if (optionChartSymbol && error instanceof ApiError && [400, 404].includes(error.status)) {
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
  }, [addToast, chartLabel, chartSecurityId, chartSymbol, optionChartSymbol, setOptionChartSymbol, timeframe])

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

        const mergedRaw = [...response.candles, ...rawCandlesRef.current].sort((a, b) => a.time - b.time)
        candlesRef.current = merged
        rawCandlesRef.current = mergedRaw
        lastBarRef.current = merged.at(-1) ?? null
        nextBeforeRef.current = response.next_before ?? null
        hasMoreHistoryRef.current = response.has_more
        series.setData(merged)
        const mergeColors = getChartColors()
        volumeSeriesRef.current?.setData(toVolumeData(mergedRaw, mergeColors.bullColor, mergeColors.bearColor))
        setCandleCount(merged.length)
        setCandleRevision((v) => v + 1)
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
          // Don't show toast for 503 on option history — limited data is expected
          if (!(optionChartSymbol && error instanceof ApiError && error.status === 503)) {
            addToast('error', error instanceof Error ? error.message : 'Failed to load older chart history')
          }
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
      setVisibleLogicalRange(range)
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

  // Periodic timer ensures live candle updates even without price changes
  // (e.g., WebSocket down, new period boundary crossed)
  useEffect(() => {
    const id = setInterval(syncLiveChartPrice, 3000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    const volumeSeries = volumeSeriesRef.current
    if (!chart || !volumeSeries) return
    try { localStorage.setItem('chart:showVolume', String(showVolume)) } catch { /* noop */ }
    if (showVolume) {
      const colors = getChartColors()
      volumeSeries.setData(toVolumeData(rawCandlesRef.current, colors.bullColor, colors.bearColor))
      chart.priceScale('right').applyOptions({ scaleMargins: { top: 0.08, bottom: 0.18 } })
      chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } })
    } else {
      volumeSeries.setData([])
      chart.priceScale('right').applyOptions({ scaleMargins: { top: 0.08, bottom: 0.02 } })
    }
  }, [showVolume])

  useEffect(() => {
    const symbol = chartQuote?.symbol ?? 'NIFTY 50'
    loadDrawingsForSymbol(symbol)
  }, [chartQuote?.symbol, loadDrawingsForSymbol])

  useEffect(() => {
    const symbol = chartQuote?.symbol ?? 'NIFTY 50'
    const symbolDrawings = overlayVisible ? (drawings[symbol] ?? []) : []
    drawingManagerRef.current?.sync(symbolDrawings)
  }, [drawings, chartQuote?.symbol, overlayVisible])

  useEffect(() => {
    if (!indicatorManagerRef.current) return
    if (!overlayVisible) {
      indicatorManagerRef.current.update([], [])
      return
    }
    indicatorManagerRef.current.update(indicators, rawCandlesRef.current)
  }, [indicators, candleRevision, overlayVisible])

  useEffect(() => {
    if (alertModal?.mode === 'edit' && !alerts.some((alert) => alert.id === alertModal.alertId)) {
      setAlertModal(null)
      setAlertDraftPrice('')
    }
  }, [alertModal, alerts])

  const chartAlerts = alerts.filter((alert) => alert.symbol === alertSymbol)
  const activeAlerts = chartAlerts.filter((alert) => alert.status === 'ACTIVE')
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
  const addButtonAnchor = shortcutAnchor
  const axisAddButtonHitbox = hasCoarsePointer ? AXIS_ADD_BUTTON_TOUCH_HITBOX : AXIS_ADD_BUTTON_HITBOX
  const axisAddButtonVisual = hasCoarsePointer ? AXIS_ADD_BUTTON_TOUCH_VISUAL : AXIS_ADD_BUTTON_VISUAL
  const axisAddButtonIconSize = hasCoarsePointer ? 12 : 10
  const alertLineHitbox = hasCoarsePointer ? ALERT_LINE_TOUCH_HITBOX : ALERT_LINE_HITBOX
  const dragThresholdPx = hasCoarsePointer ? DRAG_THRESHOLD_TOUCH_PX : DRAG_THRESHOLD_PX
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

    // Drawing drag initiation (hline/vline only, when toolbar is open and no tool active)
    if (drawingToolbar && !activeTool && seriesRef.current && chartRef.current) {
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      const x = event.clientX - rect.left
      const y = event.clientY - rect.top
      const symbol = chartQuote?.symbol ?? 'NIFTY 50'
      const symbolDrawings = drawings[symbol] ?? []

      for (const drawing of symbolDrawings) {
        if (drawing.type === 'hline') {
          const lineY = seriesRef.current.priceToCoordinate(drawing.points[0].price)
          if (lineY !== null && Math.abs(y - lineY) < 12) {
            drawingDragRef.current = { drawingId: drawing.id, symbol, startY: event.clientY, startX: event.clientX, startPrice: drawing.points[0].price, startTime: 0, type: 'hline', moved: false }
            setSelectedDrawingId(drawing.id)
            document.body.style.userSelect = 'none'
            const handleMove = (moveEvent: PointerEvent) => {
              const state = drawingDragRef.current
              if (!state || !seriesRef.current || !containerRef.current) return
              if (!state.moved && Math.abs(moveEvent.clientY - state.startY) > 5) state.moved = true
              if (!state.moved) return
              const moveRect = containerRef.current.getBoundingClientRect()
              const newPrice = seriesRef.current.coordinateToPrice(clamp(moveEvent.clientY - moveRect.top, 0, moveRect.height))
              if (newPrice !== null) {
                updateDrawing(state.symbol, state.drawingId, { points: [{ time: 0, price: Number(newPrice.toFixed(2)) }] })
              }
            }
            const handleUp = () => {
              window.removeEventListener('pointermove', handleMove)
              window.removeEventListener('pointerup', handleUp)
              document.body.style.userSelect = ''
              drawingDragRef.current = null
            }
            window.addEventListener('pointermove', handleMove)
            window.addEventListener('pointerup', handleUp)
            return
          }
        }
        if (drawing.type === 'vline') {
          const chart = chartRef.current
          const lineX = chart.timeScale().timeToCoordinate(drawing.points[0].time as Time)
          if (lineX !== null && Math.abs(x - lineX) < 12) {
            drawingDragRef.current = { drawingId: drawing.id, symbol, startY: event.clientY, startX: event.clientX, startPrice: 0, startTime: drawing.points[0].time, type: 'vline', moved: false }
            setSelectedDrawingId(drawing.id)
            document.body.style.userSelect = 'none'
            const handleMove = (moveEvent: PointerEvent) => {
              const state = drawingDragRef.current
              if (!state || !chartRef.current || !containerRef.current) return
              if (!state.moved && Math.abs(moveEvent.clientX - state.startX) > 5) state.moved = true
              if (!state.moved) return
              const moveRect = containerRef.current.getBoundingClientRect()
              const logicalX = moveEvent.clientX - moveRect.left
              // Use chart coordinate conversion to get the time at this x position
              const coord = chartRef.current.timeScale().coordinateToLogical(logicalX)
              if (coord !== null) {
                // Convert logical index back to time
                const ts = chartRef.current.timeScale().logicalToCoordinate(coord)
                if (ts !== null) {
                  // Get time from the nearest candle
                  const candles = candlesRef.current
                  const idx = clamp(Math.round(coord), 0, candles.length - 1)
                  if (candles[idx]) {
                    updateDrawing(state.symbol, state.drawingId, { points: [{ time: Number(candles[idx].time), price: 0 }] })
                  }
                }
              }
            }
            const handleUp = () => {
              window.removeEventListener('pointermove', handleMove)
              window.removeEventListener('pointerup', handleUp)
              document.body.style.userSelect = ''
              drawingDragRef.current = null
            }
            window.addEventListener('pointermove', handleMove)
            window.addEventListener('pointerup', handleUp)
            return
          }
        }
      }
    }
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
      return
    }

    if ((event.key === 'Delete' || event.key === 'Backspace') && selectedDrawingId && drawingToolbar) {
      const symbol = chartQuote?.symbol ?? 'NIFTY 50'
      removeDrawing(symbol, selectedDrawingId)
      const remaining = (drawings[symbol] ?? []).filter((d) => d.id !== selectedDrawingId)
      drawingManagerRef.current?.sync(remaining)
      setDrawingContextMenu(null)
      event.preventDefault()
    }
  }

  return (
    <div className="relative flex h-full flex-col bg-bg-primary">
      <div className={`border-b ${chartQuote ? 'border-brand/30 bg-brand/5' : 'border-border-secondary'}`}>
        {/* Row 1: Symbol + OHLC inline */}
        <div className="flex min-w-0 items-center gap-2 px-3 py-1">
          <div className="flex min-w-0 items-center gap-2">
            <span className={`shrink-0 text-[12px] font-medium ${chartQuote ? 'text-brand' : 'text-text-primary'}`}>{chartLabel}</span>
            {chartQuote && (
              <>
                <span className="shrink-0 text-[10px] text-text-muted">{chartQuote.expiry}</span>
                <button
                  onClick={() => setOptionChartSymbol(null)}
                  className="shrink-0 rounded-sm border border-border-primary bg-bg-secondary px-1.5 py-0.5 text-[10px] text-text-muted transition-colors hover:border-text-muted hover:text-text-primary"
                >
                  Back to NIFTY
                </button>
              </>
            )}
            <div className="hidden md:block h-3 w-px bg-border-primary opacity-40" />
            {hoveredCandleStats ? (
              <div className="hidden md:flex min-w-0 items-center gap-2.5 overflow-hidden whitespace-nowrap text-[11px] tabular-nums">
                <span><span className="text-text-muted">O</span> <span className={hoveredCandleStats.close >= hoveredCandleStats.open ? 'text-profit' : 'text-loss'}>{formatPrice(hoveredCandleStats.open)}</span></span>
                <span><span className="text-text-muted">H</span> <span className={hoveredCandleStats.close >= hoveredCandleStats.open ? 'text-profit' : 'text-loss'}>{formatPrice(hoveredCandleStats.high)}</span></span>
                <span><span className="text-text-muted">L</span> <span className={hoveredCandleStats.close >= hoveredCandleStats.open ? 'text-profit' : 'text-loss'}>{formatPrice(hoveredCandleStats.low)}</span></span>
                <span><span className="text-text-muted">C</span> <span className={hoveredCandleStats.close >= hoveredCandleStats.open ? 'text-profit' : 'text-loss'}>{formatPrice(hoveredCandleStats.close)}</span></span>
                {hoveredCandleStats.change != null && hoveredCandleStats.changePct != null ? (
                  <span className={hoverChangeTone}>
                    {formatSignedPrice(hoveredCandleStats.change)} ({formatSignedPercent(hoveredCandleStats.changePct)})
                  </span>
                ) : null}
              </div>
            ) : chartPrice ? (
              <span className="hidden md:inline text-[11px] tabular-nums text-text-secondary">
                {chartQuote ? 'LTP' : 'Spot'} ₹{chartPrice.toFixed(2)}
              </span>
            ) : null}
          </div>

          <div className="ml-auto flex shrink-0 items-center gap-0.5">
            <div className="max-[600px]:hidden flex items-center gap-0.5">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  onClick={() => {
                    setLoading(true)
                    setTimeframe(tf)
                  }}
                  className={`px-1.5 md:px-2 py-0.5 text-[11px] transition-colors ${
                    timeframe === tf
                      ? 'rounded-sm bg-brand text-bg-primary'
                      : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {tf}
                </button>
              ))}
              <div className="mx-1 h-3 w-px bg-border-primary opacity-50" />
            </div>
            <button
              onClick={() => setShowVolume((v) => !v)}
              className={`px-1.5 py-0.5 text-[11px] rounded-sm transition-colors ${
                showVolume
                  ? 'text-text-secondary hover:text-text-primary'
                  : 'text-text-muted line-through opacity-50 hover:opacity-75'
              }`}
              title={showVolume ? 'Hide volume' : 'Show volume'}
            >
              Vol
            </button>
            <div className="mx-1 h-3 w-px bg-border-primary opacity-50" />
            <button
              onClick={() => setDrawingToolbar(!drawingToolbar)}
              className={`flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[11px] transition-colors ${
                drawingToolbar ? 'border-brand/60 bg-brand/10 text-text-primary' : 'border-border-primary text-text-muted hover:text-text-primary'
              }`}
              title={drawingToolbar ? 'Hide drawing tools' : 'Show drawing tools'}
            >
              <Pencil size={10} />
              <span className="hidden md:inline">Draw</span>
            </button>
            <div className="mx-1 h-3 w-px bg-border-primary opacity-50" />
            <div className="relative">
              <button onClick={() => setIndicatorPanelOpen(!indicatorPanelOpen)}
                className={`flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[11px] transition-colors ${
                  indicatorPanelOpen ? 'border-brand/60 bg-brand/10 text-text-primary' : 'border-border-primary text-text-muted hover:text-text-primary'
                }`} title="Indicators">
                <BarChart2 size={10} />
                <span className="hidden md:inline">Indicators</span>
              </button>
              {indicatorPanelOpen && (
                <IndicatorPanel indicators={indicators} onToggle={toggleIndicator} onClose={() => setIndicatorPanelOpen(false)} />
              )}
            </div>
            <div className="mx-1 h-3 w-px bg-border-primary opacity-50" />
            <button
              onClick={toggleOverlayVisible}
              className={`flex items-center justify-center rounded-sm px-1 py-0.5 text-[11px] transition-colors ${
                overlayVisible ? 'text-text-muted hover:text-text-primary' : 'text-text-muted opacity-40 hover:opacity-75'
              }`}
              title={overlayVisible ? 'Hide all drawings & indicators (S)' : 'Show all drawings & indicators (S)'}
            >
              {overlayVisible ? <Eye size={12} /> : <EyeOff size={12} />}
            </button>
            <button
              onClick={() => {
                const symbol = chartQuote?.symbol ?? 'NIFTY 50'
                const count = (drawings[symbol] ?? []).length
                if (count === 0) return
                if (!confirm(`Delete all ${count} drawing${count > 1 ? 's' : ''}?`)) return
                drawingManagerRef.current?.destroy()
                clearDrawings(symbol)
                requestAnimationFrame(() => addToast('success', `Deleted ${count} drawing${count > 1 ? 's' : ''}`))
              }}
              className="flex items-center justify-center rounded-sm px-1 py-0.5 text-[11px] text-text-muted transition-colors hover:text-[#e53935]"
              title="Delete all drawings"
            >
              <Trash2 size={12} />
            </button>
            <div className="mx-1 h-3 w-px bg-border-primary opacity-50" />
            <button
              onClick={() => setAlertsPanelOpen((open) => !open)}
              className={`flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 text-[11px] transition-colors ${
                alertsPanelOpen
                  ? 'border-signal/60 bg-signal/10 text-text-primary'
                  : 'border-border-primary text-text-muted hover:text-text-primary'
              }`}
              title={alertsPanelOpen ? 'Hide alerts' : 'Show alerts'}
            >
              <Bell size={11} className="text-signal" />
              <span>{activeAlerts.length} active</span>
            </button>
          </div>
        </div>

        {/* Timeframe buttons on mobile — separate row for < 600px */}
        <div className="min-[601px]:hidden flex items-center gap-0.5 px-3 pb-1">
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

        {/* OHLC on mobile — separate row since inline won't fit */}
        {hoveredCandleStats ? (
          <div className="flex md:hidden min-w-0 items-center gap-2.5 overflow-hidden whitespace-nowrap px-3 pb-1 text-[10px] tabular-nums">
            <span><span className="text-text-muted">O</span> <span className={hoveredCandleStats.close >= hoveredCandleStats.open ? 'text-profit' : 'text-loss'}>{formatPrice(hoveredCandleStats.open)}</span></span>
            <span><span className="text-text-muted">H</span> <span className={hoveredCandleStats.close >= hoveredCandleStats.open ? 'text-profit' : 'text-loss'}>{formatPrice(hoveredCandleStats.high)}</span></span>
            <span><span className="text-text-muted">L</span> <span className={hoveredCandleStats.close >= hoveredCandleStats.open ? 'text-profit' : 'text-loss'}>{formatPrice(hoveredCandleStats.low)}</span></span>
            <span><span className="text-text-muted">C</span> <span className={hoveredCandleStats.close >= hoveredCandleStats.open ? 'text-profit' : 'text-loss'}>{formatPrice(hoveredCandleStats.close)}</span></span>
            {hoveredCandleStats.change != null && hoveredCandleStats.changePct != null ? (
              <span className={hoverChangeTone}>
                {formatSignedPrice(hoveredCandleStats.change)} ({formatSignedPercent(hoveredCandleStats.changePct)})
              </span>
            ) : null}
          </div>
        ) : chartPrice ? (
          <div className="md:hidden px-3 pb-1">
            <span className="text-[10px] tabular-nums text-text-secondary">
              {chartQuote ? 'LTP' : 'Spot'} ₹{chartPrice.toFixed(2)}
            </span>
          </div>
        ) : null}
      </div>

      <div
        ref={containerRef}
        className="relative flex-1 min-h-0 outline-none"
        tabIndex={0}
        onPointerDown={handleChartPointerDown}
        onKeyDown={handleChartKeyDown}
        onContextMenu={(e) => {
          if (!drawingToolbar) return
          e.preventDefault()
          const rect = containerRef.current?.getBoundingClientRect()
          if (!rect || !seriesRef.current) return
          const x = e.clientX - rect.left
          const y = e.clientY - rect.top
          const symbol = chartQuote?.symbol ?? 'NIFTY 50'
          const symbolDrawings = drawings[symbol] ?? []

          for (const drawing of symbolDrawings) {
            if (drawing.type === 'hline') {
              const lineY = seriesRef.current.priceToCoordinate(drawing.points[0].price)
              if (lineY !== null && Math.abs(y - lineY) < 12) {
                setDrawingContextMenu({ drawingId: drawing.id, x, y })
                setSelectedDrawingId(drawing.id)
                return
              }
            }
            if (drawing.type === 'vline') {
              const chart = chartRef.current
              if (!chart) continue
              const lineX = chart.timeScale().timeToCoordinate(drawing.points[0].time as any)
              if (lineX !== null && Math.abs(x - lineX) < 12) {
                setDrawingContextMenu({ drawingId: drawing.id, x, y })
                setSelectedDrawingId(drawing.id)
                return
              }
            }
            // For other drawing types, do a simple bounding-box check
            if (drawing.points.length >= 2) {
              const p1 = seriesRef.current.priceToCoordinate(drawing.points[0].price)
              const p2 = seriesRef.current.priceToCoordinate(drawing.points[1].price)
              const chart = chartRef.current
              if (!p1 || !p2 || !chart) continue
              const x1 = chart.timeScale().timeToCoordinate(drawing.points[0].time as any)
              const x2 = chart.timeScale().timeToCoordinate(drawing.points[1].time as any)
              if (x1 === null || x2 === null) continue
              const minX = Math.min(x1, x2) - 12
              const maxX = Math.max(x1, x2) + 12
              const minY = Math.min(p1, p2) - 12
              const maxY = Math.max(p1, p2) + 12
              if (x >= minX && x <= maxX && y >= minY && y <= maxY) {
                setDrawingContextMenu({ drawingId: drawing.id, x, y })
                setSelectedDrawingId(drawing.id)
                return
              }
            }
          }
        }}
      >
        {drawingToolbar && (
          <DrawingToolbar
            activeTool={activeTool}
            onSelectTool={setActiveTool}
            onClearAll={() => {
              const symbol = chartQuote?.symbol ?? 'NIFTY 50'
              const count = (drawings[symbol] ?? []).length
              if (count === 0) return
              if (!confirm(`Delete all ${count} drawing${count > 1 ? 's' : ''}?`)) return
              drawingManagerRef.current?.destroy()
              clearDrawings(symbol)
              requestAnimationFrame(() => addToast('success', `Deleted ${count} drawing${count > 1 ? 's' : ''}`))
            }}
            isCoarsePointer={hasCoarsePointer}
          />
        )}
        {activeTool && (
          <div className="pointer-events-none absolute left-10 top-2 z-30 rounded bg-[#1e1e1e]/80 px-2 py-1 text-[10px] text-text-muted backdrop-blur-sm">
            {activeTool === 'hline' ? 'Click to place horizontal line' :
             activeTool === 'vline' ? 'Click to place vertical line' :
             activeTool === 'channel' && drawingInProgress?.length === 2 ? 'Click to set channel width' :
             drawingInProgress?.length === 1 ? 'Click second point' :
             'Click first point'}
          </div>
        )}
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
                  className={`pointer-events-auto absolute inset-x-0 top-0 -translate-y-1/2 ${
                    alertMutation ? 'cursor-wait' : 'cursor-grab active:cursor-grabbing'
                  }`}
                  style={{ height: alertLineHitbox, touchAction: 'none' }}
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

          {addButtonAnchor && !alertModal ? (
            <div
              data-alert-interactive="true"
              className="pointer-events-auto absolute z-20 flex -translate-y-1/2 items-center justify-center"
              style={{
                right: AXIS_ADD_BUTTON_RIGHT - ((axisAddButtonHitbox - axisAddButtonVisual) / 2),
                top: clamp(addButtonAnchor.y, 0, containerHeight || 0),
                width: axisAddButtonHitbox,
                height: axisAddButtonHitbox,
              }}
            >
              <button
                data-alert-interactive="true"
                onPointerDown={(event) => {
                  event.preventDefault()
                  event.stopPropagation()
                  openCreateAlertModal(addButtonAnchor)
                }}
                className="group flex h-full w-full items-center justify-center text-text-muted transition-colors hover:text-signal"
                style={{ touchAction: 'manipulation' }}
                title="Create alert (A)"
              >
                <span
                  className="flex items-center justify-center rounded-full border border-border-primary/80 bg-bg-secondary/88 shadow-sm backdrop-blur transition-colors group-hover:border-signal/60"
                  style={{ width: axisAddButtonVisual, height: axisAddButtonVisual }}
                >
                  <Plus size={axisAddButtonIconSize} />
                </span>
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

        {drawingContextMenu && (() => {
          const symbol = chartQuote?.symbol ?? 'NIFTY 50'
          const drawing = (drawings[symbol] ?? []).find((d) => d.id === drawingContextMenu.drawingId)
          if (!drawing) return null
          return (
            <DrawingContextMenu
              x={drawingContextMenu.x} y={drawingContextMenu.y} style={drawing.style}
              onChangeStyle={(updates) => updateDrawing(symbol, drawing.id, { style: { ...drawing.style, ...updates } })}
              onDelete={() => {
                removeDrawing(symbol, drawing.id)
                const remaining = (drawings[symbol] ?? []).filter((d) => d.id !== drawing.id)
                drawingManagerRef.current?.sync(remaining)
                setDrawingContextMenu(null)
              }}
              onClose={() => setDrawingContextMenu(null)}
            />
          )
        })()}
      </div>
      {overlayVisible && indicators.filter((ind) => ind.enabled && OSCILLATOR_INDICATORS.includes(ind.type)).map((ind) => {
        const raw = rawCandlesRef.current
        let data: { time: number; value: number }[] = []
        let extraLines: { data: { time: number; value: number }[]; color: string }[] | undefined
        let histogram: { time: number; value: number }[] | undefined
        let currentValue: number | null = null

        if (ind.type === 'rsi') {
          data = computeRSI(raw, ind.params.period)
          currentValue = data.length > 0 ? data[data.length - 1].value : null
        } else if (ind.type === 'macd') {
          const macdData = computeMACD(raw, ind.params.fast, ind.params.slow, ind.params.signal)
          data = macdData.map((d) => ({ time: d.time, value: d.macd }))
          extraLines = [{ data: macdData.map((d) => ({ time: d.time, value: d.signal })), color: '#e53935' }]
          histogram = macdData.map((d) => ({ time: d.time, value: d.histogram }))
          currentValue = macdData.length > 0 ? macdData[macdData.length - 1].macd : null
        } else if (ind.type === 'adx') {
          const adxData = computeADX(raw, ind.params.period)
          data = adxData.map((d) => ({ time: d.time, value: d.adx }))
          extraLines = [
            { data: adxData.map((d) => ({ time: d.time, value: d.plusDI })), color: '#4caf50' },
            { data: adxData.map((d) => ({ time: d.time, value: d.minusDI })), color: '#e53935' },
          ]
          currentValue = adxData.length > 0 ? adxData[adxData.length - 1].adx : null
        }

        return (
          <OscillatorPane key={ind.id} config={ind} data={data} extraLines={extraLines} histogram={histogram}
            expanded={oscillatorPaneState[ind.id] !== false} currentValue={currentValue} visibleRange={visibleLogicalRange}
            onToggleExpanded={() => setOscillatorPaneExpanded(ind.id, oscillatorPaneState[ind.id] === false)}
            onRemove={() => toggleIndicator(ind.id)} />
        )
      })}
    </div>
  )
}
