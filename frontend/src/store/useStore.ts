import { create } from 'zustand'

import type { Drawing, DrawingType, DrawingPoint, IndicatorConfig } from '../lib/chart/types'
import { loadDrawings, saveDrawings, saveDrawingsDebounced, loadIndicatorConfigs, saveIndicatorConfigsDebounced } from '../lib/chart/storage'

import type {
  AlertSummary,
  AnalyticsResponse,
  FundsResponse,
  MarketSnapshot,
  OptionChainResponse,
  OptionQuote,
  OrderSummary,
  PortfolioSummary,
  PositionSummary,
  QuoteBatchEvent,
  QuotePatch,
  SignalResponse,
  UserSummary,
} from '../lib/api'

type ToastType = 'success' | 'error' | 'info'
type ChainSide = 'call' | 'put'
type ChainIndex = Record<string, { rowIndex: number; side: ChainSide }>
type RuntimeOptionQuote = OptionQuote & { oi_lakhs?: number | null }

const ALLOWED_QUOTE_PATCH_KEYS = [
  'security_id',
  'strike',
  'option_type',
  'expiry',
  'ltp',
  'bid',
  'ask',
  'bid_qty',
  'ask_qty',
  'iv',
  'oi',
  'oi_lakhs',
  'volume',
  'day_high',
  'day_low',
  'delta',
  'gamma',
  'theta',
  'vega',
] as const

interface Toast {
  id: string
  type: ToastType
  message: string
}

interface AppState {
  accessToken: string | null
  user: UserSummary | null
  sharedLoading: boolean
  portfolioLoading: boolean
  chainLoading: boolean
  wsStatus: 'connected' | 'connecting' | 'disconnected'
  snapshot: MarketSnapshot | null
  chain: OptionChainResponse | null
  chainIndex: ChainIndex
  portfolios: PortfolioSummary[]
  portfoliosLoaded: boolean
  selectedPortfolioId: string
  selectedExpiry: string | null
  selectedQuote: OptionQuote | null
  orders: OrderSummary[]
  positions: PositionSummary[]
  funds: FundsResponse | null
  analytics: AnalyticsResponse | null
  latestSignal: SignalResponse | null
  alerts: AlertSummary[]
  triggeredAlertQueue: AlertSummary[]
  chartTimeframe: '1m' | '5m' | '15m' | '1h' | 'D' | 'W' | 'M'
  chainView: 'collapsed' | 'expanded'
  chainFilter: 'ALL' | 'ITM' | 'ATM' | 'OTM'
  chainPanelOpen: boolean
  optionChartSymbol: string | null
  portfolioRefreshNonce: number
  toasts: Toast[]
  orderModal: { isOpen: boolean; quote: OptionQuote; side: 'BUY' | 'SELL' } | null
  drawingToolbar: boolean
  activeTool: DrawingType | null
  drawings: Record<string, Drawing[]>
  selectedDrawingId: string | null
  drawingInProgress: DrawingPoint[] | null
  indicatorPanelOpen: boolean
  indicators: IndicatorConfig[]
  oscillatorPaneState: Record<string, boolean>
  overlayVisible: boolean
  setChartTimeframe: (tf: AppState['chartTimeframe']) => void
  setChainView: (view: AppState['chainView']) => void
  setChainFilter: (filter: AppState['chainFilter']) => void
  setChainPanelOpen: (open: boolean) => void
  setOptionChartSymbol: (symbol: string | null) => void
  openOrderModal: (quote: OptionQuote, side: 'BUY' | 'SELL') => void
  closeOrderModal: () => void
  setSession: (token: string | null, user: UserSummary | null) => void
  setSharedLoading: (loading: boolean) => void
  setPortfolioLoading: (loading: boolean) => void
  setChainLoading: (loading: boolean) => void
  setWsStatus: (status: AppState['wsStatus']) => void
  setSnapshot: (snapshot: MarketSnapshot | null) => void
  setChain: (chain: OptionChainResponse | null) => void
  setPortfolios: (portfolios: PortfolioSummary[]) => void
  setSelectedPortfolioId: (id: string) => void
  setSelectedExpiry: (expiry: string | null) => void
  setSelectedQuote: (quote: OptionQuote | null) => void
  setOrders: (orders: OrderSummary[]) => void
  setPositions: (positions: PositionSummary[]) => void
  setFunds: (funds: FundsResponse | null) => void
  setAnalytics: (analytics: AnalyticsResponse | null) => void
  setLatestSignal: (signal: SignalResponse | null) => void
  setAlerts: (alerts: AlertSummary[]) => void
  upsertAlert: (alert: AlertSummary) => void
  enqueueTriggeredAlert: (alert: AlertSummary) => void
  removeAlert: (alertId: string) => void
  dismissTriggeredAlert: (alertId: string) => void
  upsertSignal: (signal: SignalResponse) => void
  applyChainEvent: (chain: OptionChainResponse) => void
  applyQuoteBatch: (event: QuoteBatchEvent) => void
  requestPortfolioRefresh: (portfolioId?: string | null) => void
  addToast: (type: ToastType, message: string) => void
  removeToast: (id: string) => void
  setDrawingToolbar: (open: boolean) => void
  setActiveTool: (tool: DrawingType | null) => void
  setSelectedDrawingId: (id: string | null) => void
  setDrawingInProgress: (points: DrawingPoint[] | null) => void
  addDrawing: (symbol: string, drawing: Drawing) => void
  updateDrawing: (symbol: string, id: string, updates: Partial<Drawing>) => void
  removeDrawing: (symbol: string, id: string) => void
  clearDrawings: (symbol: string) => void
  loadDrawingsForSymbol: (symbol: string) => void
  setIndicatorPanelOpen: (open: boolean) => void
  toggleIndicator: (id: string) => void
  setOscillatorPaneExpanded: (id: string, expanded: boolean) => void
  toggleOverlayVisible: () => void
}

function initialUserScopedState(): Pick<
  AppState,
  | 'accessToken'
  | 'user'
  | 'sharedLoading'
  | 'portfolioLoading'
  | 'chainLoading'
  | 'wsStatus'
  | 'snapshot'
  | 'chain'
  | 'chainIndex'
  | 'portfolios'
  | 'portfoliosLoaded'
  | 'selectedPortfolioId'
  | 'selectedExpiry'
  | 'selectedQuote'
  | 'orders'
  | 'positions'
  | 'funds'
  | 'analytics'
  | 'latestSignal'
  | 'alerts'
  | 'triggeredAlertQueue'
  | 'optionChartSymbol'
  | 'portfolioRefreshNonce'
  | 'orderModal'
> {
  return {
    accessToken: null,
    user: null,
    sharedLoading: false,
    portfolioLoading: false,
    chainLoading: false,
    wsStatus: 'disconnected',
    snapshot: null,
    chain: null,
    chainIndex: {},
    portfolios: [],
    portfoliosLoaded: false,
    selectedPortfolioId: '',
    selectedExpiry: null,
    selectedQuote: null,
    orders: [],
    positions: [],
    funds: null,
    analytics: null,
    latestSignal: null,
    alerts: [],
    triggeredAlertQueue: [],
    optionChartSymbol: null,
    portfolioRefreshNonce: 0,
    orderModal: null,
  }
}

function sortAlerts(alerts: AlertSummary[]): AlertSummary[] {
  return [...alerts].sort((left, right) => {
    const statusOrder = { ACTIVE: 0, TRIGGERED: 1, CANCELLED: 2 } as const
    const leftRank = statusOrder[left.status] ?? 99
    const rightRank = statusOrder[right.status] ?? 99
    if (leftRank !== rightRank) {
      return leftRank - rightRank
    }
    return new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
  })
}

function upsertAlertRecord(alerts: AlertSummary[], alert: AlertSummary): AlertSummary[] {
  const nextAlerts = alerts.filter((item) => item.id !== alert.id)
  if (alert.status !== 'CANCELLED') {
    nextAlerts.push(alert)
  }
  return sortAlerts(nextAlerts)
}

function roundMoney(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100
}

function sameExpiries(current: readonly string[] | undefined, next: readonly string[] | undefined): boolean {
  if (current === next) {
    return true
  }
  if (!current || !next || current.length !== next.length) {
    return false
  }
  return current.every((value, index) => value === next[index])
}

function stabilizeSnapshot(previous: MarketSnapshot | null, next: MarketSnapshot | null): MarketSnapshot | null {
  if (!next) {
    return null
  }
  if (!previous || !sameExpiries(previous.expiries, next.expiries)) {
    return next
  }
  return {
    ...next,
    expiries: previous.expiries,
  }
}

function resolveSelectedExpiry(
  selectedExpiry: string | null,
  snapshot: Pick<MarketSnapshot, 'expiries' | 'active_expiry'> | null | undefined,
): string | null {
  const expiries = snapshot?.expiries ?? []
  if (!expiries.length) {
    return selectedExpiry ?? snapshot?.active_expiry ?? null
  }
  if (selectedExpiry && expiries.includes(selectedExpiry)) {
    return selectedExpiry
  }
  if (snapshot?.active_expiry && expiries.includes(snapshot.active_expiry)) {
    return snapshot.active_expiry
  }
  return expiries[0] ?? null
}

function buildChainIndex(chain: OptionChainResponse | null): ChainIndex {
  if (!chain) {
    return {}
  }
  return chain.rows.reduce<ChainIndex>((acc, row, rowIndex) => {
    acc[row.call.symbol] = { rowIndex, side: 'call' }
    acc[row.put.symbol] = { rowIndex, side: 'put' }
    return acc
  }, {})
}

function resolveIndexedQuote(
  chain: OptionChainResponse | null,
  chainIndex: ChainIndex,
  symbol: string,
): RuntimeOptionQuote | null {
  if (!chain) {
    return null
  }
  const location = chainIndex[symbol]
  if (!location) {
    return null
  }
  const row = chain.rows[location.rowIndex]
  if (!row) {
    return null
  }
  return location.side === 'call' ? row.call : row.put
}

function sanitizeQuotePatch(patch: QuotePatch): QuotePatch | null {
  if (!patch || typeof patch.symbol !== 'string' || !patch.symbol) {
    return null
  }
  const nextPatch: QuotePatch = { symbol: patch.symbol }
  const nextPatchRecord = nextPatch as Record<string, unknown>
  for (const key of ALLOWED_QUOTE_PATCH_KEYS) {
    const value = patch[key]
    if (value !== undefined) {
      nextPatchRecord[key] = value
    }
  }
  return nextPatch
}

function mergeQuote(current: RuntimeOptionQuote, patch: QuotePatch): RuntimeOptionQuote {
  let changed = false
  const next: RuntimeOptionQuote = { ...current }
  const nextRecord = next as Record<string, unknown>

  for (const key of ALLOWED_QUOTE_PATCH_KEYS) {
    const value = patch[key]
    if (value === undefined || nextRecord[key] === value) {
      continue
    }
    nextRecord[key] = value
    changed = true
  }

  return changed ? next : current
}

function computeUnrealized(position: PositionSummary): number {
  if (position.net_quantity === 0) {
    return 0
  }
  if (position.net_quantity > 0) {
    return roundMoney((position.last_price - position.average_open_price) * position.net_quantity)
  }
  return roundMoney((position.average_open_price - position.last_price) * Math.abs(position.net_quantity))
}

function syncPositionsFromChain(
  positions: PositionSummary[],
  chain: OptionChainResponse | null,
  chainIndex: ChainIndex,
): PositionSummary[] {
  if (!positions.length || !chain) {
    return positions
  }
  let changed = false
  const nextPositions = positions.map((position) => {
    const quote = resolveIndexedQuote(chain, chainIndex, position.symbol)
    if (!quote || quote.ltp === position.last_price) {
      return position
    }
    changed = true
    const next = { ...position, last_price: quote.ltp }
    next.unrealized_pnl = computeUnrealized(next)
    return next
  })
  return changed ? nextPositions : positions
}

function syncPositionsFromPatches(
  positions: PositionSummary[],
  patches: Map<string, QuotePatch>,
): PositionSummary[] {
  if (!positions.length || !patches.size) {
    return positions
  }
  let changed = false
  const nextPositions = positions.map((position) => {
    const patch = patches.get(position.symbol)
    const nextPrice = patch?.ltp
    if (nextPrice == null || nextPrice === position.last_price) {
      return position
    }
    changed = true
    const next = { ...position, last_price: nextPrice }
    next.unrealized_pnl = computeUnrealized(next)
    return next
  })
  return changed ? nextPositions : positions
}

function derivePortfolioMetrics(
  positions: PositionSummary[],
  funds: FundsResponse | null,
  analytics: AnalyticsResponse | null,
): Pick<AppState, 'funds' | 'analytics'> {
  const unrealized = roundMoney(positions.reduce((sum, position) => sum + position.unrealized_pnl, 0))
  const cashBase = funds
    ? funds.cash_balance
    : analytics
      ? analytics.total_equity - analytics.unrealized_pnl
      : null

  return {
    funds: funds
      ? {
          ...funds,
          unrealized_pnl: unrealized,
          total_equity: roundMoney(funds.cash_balance + unrealized),
        }
      : funds,
    analytics: analytics && cashBase != null
      ? {
          ...analytics,
          unrealized_pnl: unrealized,
          total_equity: roundMoney(cashBase + unrealized),
        }
      : analytics,
  }
}

function syncSelectedQuote(
  selectedQuote: OptionQuote | null,
  chain: OptionChainResponse | null,
  chainIndex: ChainIndex,
): OptionQuote | null {
  if (!selectedQuote) {
    return null
  }
  return resolveIndexedQuote(chain, chainIndex, selectedQuote.symbol) ?? selectedQuote
}

export const useStore = create<AppState>((set, get) => ({
  ...initialUserScopedState(),
  chartTimeframe: 'D',
  chainView: 'collapsed',
  chainFilter: 'ATM',
  chainPanelOpen: true,
  toasts: [],
  drawingToolbar: false,
  activeTool: null,
  drawings: {},
  selectedDrawingId: null,
  drawingInProgress: null,
  indicatorPanelOpen: false,
  indicators: loadIndicatorConfigs(),
  oscillatorPaneState: {},
  overlayVisible: true,
  setChartTimeframe: (chartTimeframe) => set({ chartTimeframe }),
  setChainView: (chainView) => set({ chainView }),
  setChainFilter: (chainFilter) => set({ chainFilter }),
  setChainPanelOpen: (chainPanelOpen) => set({ chainPanelOpen }),
  setOptionChartSymbol: (optionChartSymbol) => set({ optionChartSymbol }),
  openOrderModal: (quote, side) => set({ orderModal: { isOpen: true, quote, side } }),
  closeOrderModal: () => set({ orderModal: null }),
  setSession: (token, user) => set((state) => {
    if (!token || !user) {
      return initialUserScopedState()
    }
    if (state.user?.id && state.user.id !== user.id) {
      return { ...initialUserScopedState(), accessToken: token, user }
    }
    return { accessToken: token, user }
  }),
  setSharedLoading: (sharedLoading) => set({ sharedLoading }),
  setPortfolioLoading: (portfolioLoading) => set({ portfolioLoading }),
  setChainLoading: (chainLoading) => set({ chainLoading }),
  setWsStatus: (wsStatus) => set({ wsStatus }),
  setSnapshot: (snapshot) => set((state) => {
    const nextSnapshot = stabilizeSnapshot(state.snapshot, snapshot)
    return {
      snapshot: nextSnapshot,
      selectedExpiry: resolveSelectedExpiry(state.selectedExpiry, nextSnapshot),
    }
  }),
  setChain: (chain) => set((state) => {
    const chainIndex = buildChainIndex(chain)
    const positions = syncPositionsFromChain(state.positions, chain, chainIndex)
    const selectedQuote = syncSelectedQuote(state.selectedQuote, chain, chainIndex)
    const derived = derivePortfolioMetrics(positions, state.funds, state.analytics)
    const snapshot = stabilizeSnapshot(state.snapshot, chain?.snapshot ?? state.snapshot)
    const optionChartSymbol = state.optionChartSymbol && chainIndex[state.optionChartSymbol]
      ? state.optionChartSymbol
      : null

    return {
      chain,
      chainIndex,
      snapshot,
      selectedExpiry: resolveSelectedExpiry(state.selectedExpiry, chain?.snapshot),
      selectedQuote,
      optionChartSymbol,
      positions,
      funds: derived.funds,
      analytics: derived.analytics,
    }
  }),
  setPortfolios: (portfolios) => set((state) => ({
    portfolios,
    portfoliosLoaded: true,
    selectedPortfolioId: portfolios.some((item) => item.id === state.selectedPortfolioId)
      ? state.selectedPortfolioId
      : (portfolios.find((item) => item.kind === 'manual')?.id ?? portfolios[0]?.id ?? ''),
  })),
  setSelectedPortfolioId: (selectedPortfolioId) => set({ selectedPortfolioId }),
  setSelectedExpiry: (selectedExpiry) => set({ selectedExpiry }),
  setSelectedQuote: (selectedQuote) => set({ selectedQuote }),
  setOrders: (orders) => set({ orders }),
  setPositions: (positions) => set((state) => {
    const nextPositions = syncPositionsFromChain(positions, state.chain, state.chainIndex)
    const derived = derivePortfolioMetrics(nextPositions, state.funds, state.analytics)
    return {
      positions: nextPositions,
      funds: derived.funds,
      analytics: derived.analytics,
    }
  }),
  setFunds: (funds) => set((state) => {
    const derived = derivePortfolioMetrics(state.positions, funds, state.analytics)
    return { funds: derived.funds, analytics: derived.analytics }
  }),
  setAnalytics: (analytics) => set((state) => {
    const derived = derivePortfolioMetrics(state.positions, state.funds, analytics)
    return { funds: derived.funds, analytics: derived.analytics }
  }),
  setLatestSignal: (latestSignal) => set({ latestSignal }),
  setAlerts: (alerts) => set((state) => {
    const visibleAlerts = sortAlerts(alerts.filter((alert) => alert.status !== 'CANCELLED'))
    return {
      alerts: visibleAlerts,
      triggeredAlertQueue: state.triggeredAlertQueue.filter((queued) => visibleAlerts.some((alert) => alert.id === queued.id && alert.status === 'TRIGGERED')),
    }
  }),
  upsertAlert: (alert) => set((state) => ({
    alerts: upsertAlertRecord(state.alerts, alert),
    triggeredAlertQueue: alert.status === 'TRIGGERED'
      ? state.triggeredAlertQueue.map((queued) => (queued.id === alert.id ? alert : queued))
      : state.triggeredAlertQueue.filter((queued) => queued.id !== alert.id),
  })),
  enqueueTriggeredAlert: (alert) => set((state) => ({
    alerts: upsertAlertRecord(state.alerts, alert),
    triggeredAlertQueue: state.triggeredAlertQueue.some((queued) => queued.id === alert.id)
      ? state.triggeredAlertQueue.map((queued) => (queued.id === alert.id ? alert : queued))
      : [...state.triggeredAlertQueue, alert],
  })),
  removeAlert: (alertId) => set((state) => ({
    alerts: state.alerts.filter((alert) => alert.id !== alertId),
    triggeredAlertQueue: state.triggeredAlertQueue.filter((alert) => alert.id !== alertId),
  })),
  dismissTriggeredAlert: (alertId) => set((state) => ({
    triggeredAlertQueue: state.triggeredAlertQueue.filter((alert) => alert.id !== alertId),
  })),
  upsertSignal: (latestSignal) => set({ latestSignal }),
  applyChainEvent: (chain) => set((state) => {
    const chainIndex = buildChainIndex(chain)
    const positions = syncPositionsFromChain(state.positions, chain, chainIndex)
    const selectedQuote = syncSelectedQuote(state.selectedQuote, chain, chainIndex)
    const derived = derivePortfolioMetrics(positions, state.funds, state.analytics)
    const snapshot = stabilizeSnapshot(state.snapshot, chain.snapshot)
    const optionChartSymbol = state.optionChartSymbol && chainIndex[state.optionChartSymbol]
      ? state.optionChartSymbol
      : null

    return {
      chain,
      chainIndex,
      snapshot,
      selectedExpiry: resolveSelectedExpiry(state.selectedExpiry, chain.snapshot),
      selectedQuote,
      optionChartSymbol,
      positions,
      funds: derived.funds,
      analytics: derived.analytics,
    }
  }),
  applyQuoteBatch: (event) => set((state) => {
    const patchMap = new Map<string, QuotePatch>()

    for (const patch of event.quotes) {
      const nextPatch = sanitizeQuotePatch(patch)
      if (nextPatch) {
        patchMap.set(nextPatch.symbol, nextPatch)
      }
    }

    const nextSnapshot = state.snapshot && state.snapshot.active_expiry === event.active_expiry
      ? stabilizeSnapshot(state.snapshot, { ...state.snapshot, updated_at: event.updated_at })
      : state.snapshot

    if (!state.chain || !patchMap.size) {
      return nextSnapshot === state.snapshot ? {} : { snapshot: nextSnapshot }
    }

    let rowsChanged = false
    const rows = state.chain.rows.slice()

    for (const [symbol, patch] of patchMap) {
      const location = state.chainIndex[symbol]
      if (!location) {
        continue
      }
      const currentRow = rows[location.rowIndex]
      if (!currentRow) {
        continue
      }
      const currentQuote = location.side === 'call' ? currentRow.call as RuntimeOptionQuote : currentRow.put as RuntimeOptionQuote
      const nextQuote = mergeQuote(currentQuote, patch)
      if (nextQuote === currentQuote) {
        continue
      }
      const nextRow = rows[location.rowIndex] === currentRow ? { ...currentRow } : rows[location.rowIndex]
      nextRow[location.side] = nextQuote
      rows[location.rowIndex] = nextRow
      rowsChanged = true
    }

    const chain = rowsChanged
      ? {
          ...state.chain,
          rows,
          snapshot: nextSnapshot ?? state.chain.snapshot,
        }
      : state.chain

    const positions = syncPositionsFromPatches(state.positions, patchMap)
    const selectedQuote = state.selectedQuote
      ? (
          patchMap.has(state.selectedQuote.symbol)
            ? resolveIndexedQuote(chain, state.chainIndex, state.selectedQuote.symbol) ?? state.selectedQuote
            : state.selectedQuote
        )
      : null
    const derived = derivePortfolioMetrics(positions, state.funds, state.analytics)

    return {
      chain,
      snapshot: nextSnapshot,
      selectedQuote,
      positions,
      funds: derived.funds,
      analytics: derived.analytics,
    }
  }),
  requestPortfolioRefresh: (portfolioId) => set((state) => ({
    portfolioRefreshNonce:
      !portfolioId || portfolioId === state.selectedPortfolioId
        ? state.portfolioRefreshNonce + 1
        : state.portfolioRefreshNonce,
  })),
  addToast: (type, message) => {
    const id = crypto.randomUUID()
    set((state) => ({ toasts: [...state.toasts, { id, type, message }] }))
    window.setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) }))
    }, 5000)
  },
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
  setDrawingToolbar: (open) => set({ drawingToolbar: open, activeTool: open ? null : get().activeTool }),
  setActiveTool: (tool) => set({ activeTool: tool, selectedDrawingId: null, drawingInProgress: null }),
  setSelectedDrawingId: (id) => set({ selectedDrawingId: id }),
  setDrawingInProgress: (points) => set({ drawingInProgress: points }),
  addDrawing: (symbol, drawing) => {
    const current = get().drawings[symbol] ?? []
    set({ drawings: { ...get().drawings, [symbol]: [...current, drawing] } })
    saveDrawingsDebounced(symbol, [...current, drawing])
  },
  updateDrawing: (symbol, id, updates) => {
    const current = get().drawings[symbol] ?? []
    const updated = current.map((d) => (d.id === id ? { ...d, ...updates } : d))
    set({ drawings: { ...get().drawings, [symbol]: updated } })
    saveDrawingsDebounced(symbol, updated)
  },
  removeDrawing: (symbol, id) => {
    const current = get().drawings[symbol] ?? []
    const filtered = current.filter((d) => d.id !== id)
    set({ drawings: { ...get().drawings, [symbol]: filtered }, selectedDrawingId: null })
    saveDrawingsDebounced(symbol, filtered)
  },
  clearDrawings: (symbol) => {
    set({ drawings: { ...get().drawings, [symbol]: [] }, selectedDrawingId: null })
    saveDrawings(symbol, [])
  },
  loadDrawingsForSymbol: (symbol) => {
    if (get().drawings[symbol]) return
    set({ drawings: { ...get().drawings, [symbol]: loadDrawings(symbol) } })
  },
  setIndicatorPanelOpen: (open) => set({ indicatorPanelOpen: open }),
  toggleIndicator: (id) => {
    const indicators = get().indicators.map((ind) =>
      ind.id === id ? { ...ind, enabled: !ind.enabled } : ind
    )
    set({ indicators })
    saveIndicatorConfigsDebounced(indicators)
  },
  setOscillatorPaneExpanded: (id, expanded) => {
    set({ oscillatorPaneState: { ...get().oscillatorPaneState, [id]: expanded } })
  },
  toggleOverlayVisible: () => set({ overlayVisible: !get().overlayVisible }),
}))
