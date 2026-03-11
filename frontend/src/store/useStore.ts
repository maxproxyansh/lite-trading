import { create } from 'zustand'

import type {
  AnalyticsResponse,
  FundsResponse,
  MarketSnapshot,
  OptionChainResponse,
  OptionQuote,
  OrderSummary,
  PortfolioSummary,
  PositionSummary,
  SignalResponse,
  UserSummary,
} from '../lib/api'

type ToastType = 'success' | 'error' | 'info'

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
  chainView: 'collapsed' | 'expanded'
  chainFilter: 'ALL' | 'ITM' | 'ATM' | 'OTM'
  chainPanelOpen: boolean
  optionChartSymbol: string | null
  toasts: Toast[]
  orderModal: { isOpen: boolean; quote: OptionQuote; side: 'BUY' | 'SELL' } | null
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
  upsertSignal: (signal: SignalResponse) => void
  applyChainEvent: (chain: OptionChainResponse) => void
  addToast: (type: ToastType, message: string) => void
  removeToast: (id: string) => void
}

export const useStore = create<AppState>((set) => ({
  accessToken: null,
  user: null,
  sharedLoading: false,
  portfolioLoading: false,
  chainLoading: false,
  wsStatus: 'disconnected',
  snapshot: null,
  chain: null,
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
  toasts: [],
  chainView: 'collapsed',
  chainFilter: 'ATM',
  chainPanelOpen: true,
  optionChartSymbol: null,
  setChainView: (chainView) => set({ chainView }),
  setChainFilter: (chainFilter) => set({ chainFilter }),
  setChainPanelOpen: (chainPanelOpen) => set({ chainPanelOpen }),
  setOptionChartSymbol: (optionChartSymbol) => set({ optionChartSymbol }),
  orderModal: null,
  openOrderModal: (quote, side) => set({ orderModal: { isOpen: true, quote, side } }),
  closeOrderModal: () => set({ orderModal: null }),
  setSession: (token, user) => set({ accessToken: token, user }),
  setSharedLoading: (sharedLoading) => set({ sharedLoading }),
  setPortfolioLoading: (portfolioLoading) => set({ portfolioLoading }),
  setChainLoading: (chainLoading) => set({ chainLoading }),
  setWsStatus: (wsStatus) => set({ wsStatus }),
  setSnapshot: (snapshot) => set((state) => ({
    snapshot,
    selectedExpiry: state.selectedExpiry ?? snapshot?.active_expiry ?? null,
  })),
  setChain: (chain) => set((state) => ({
    chain,
    snapshot: chain?.snapshot ?? state.snapshot,
    selectedExpiry: state.selectedExpiry ?? chain?.snapshot.active_expiry ?? null,
  })),
  setPortfolios: (portfolios) => set((state) => ({
    portfolios,
    portfoliosLoaded: true,
    selectedPortfolioId: portfolios.some((item) => item.id === state.selectedPortfolioId)
      ? state.selectedPortfolioId
      : (portfolios[0]?.id ?? ''),
  })),
  setSelectedPortfolioId: (selectedPortfolioId) => set({ selectedPortfolioId }),
  setSelectedExpiry: (selectedExpiry) => set({ selectedExpiry }),
  setSelectedQuote: (selectedQuote) => set({ selectedQuote }),
  setOrders: (orders) => set({ orders }),
  setPositions: (positions) => set({ positions }),
  setFunds: (funds) => set({ funds }),
  setAnalytics: (analytics) => set({ analytics }),
  setLatestSignal: (latestSignal) => set({ latestSignal }),
  upsertSignal: (latestSignal) => set({ latestSignal }),
  applyChainEvent: (chain) => set((state) => {
    const nextSelected = state.selectedQuote
      ? chain.rows.flatMap((row) => [row.call, row.put]).find((quote) => quote.symbol === state.selectedQuote?.symbol) ?? state.selectedQuote
      : null
    return {
      chain,
      snapshot: chain.snapshot,
      selectedExpiry: state.selectedExpiry ?? chain.snapshot.active_expiry ?? null,
      selectedQuote: nextSelected,
    }
  }),
  addToast: (type, message) => {
    const id = crypto.randomUUID()
    set((state) => ({ toasts: [...state.toasts, { id, type, message }] }))
    window.setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) }))
    }, 5000)
  },
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
}))
