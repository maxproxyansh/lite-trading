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
  wsStatus: 'connected' | 'connecting' | 'disconnected'
  snapshot: MarketSnapshot | null
  chain: OptionChainResponse | null
  portfolios: PortfolioSummary[]
  selectedPortfolioId: string
  selectedExpiry: string | null
  selectedQuote: OptionQuote | null
  orders: OrderSummary[]
  positions: PositionSummary[]
  funds: FundsResponse | null
  analytics: AnalyticsResponse | null
  latestSignal: SignalResponse | null
  toasts: Toast[]
  setSession: (token: string | null, user: UserSummary | null) => void
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

const ACCESS_TOKEN_KEY = 'lite-access-token'
const USER_KEY = 'lite-user'

function readStoredUser(): UserSummary | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) as UserSummary : null
  } catch {
    return null
  }
}

export const useStore = create<AppState>((set) => ({
  accessToken: localStorage.getItem(ACCESS_TOKEN_KEY),
  user: readStoredUser(),
  wsStatus: 'disconnected',
  snapshot: null,
  chain: null,
  portfolios: [],
  selectedPortfolioId: 'manual',
  selectedExpiry: null,
  selectedQuote: null,
  orders: [],
  positions: [],
  funds: null,
  analytics: null,
  latestSignal: null,
  toasts: [],
  setSession: (token, user) => {
    if (token) {
      localStorage.setItem(ACCESS_TOKEN_KEY, token)
    } else {
      localStorage.removeItem(ACCESS_TOKEN_KEY)
    }
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    } else {
      localStorage.removeItem(USER_KEY)
    }
    set({ accessToken: token, user })
  },
  setWsStatus: (wsStatus) => set({ wsStatus }),
  setSnapshot: (snapshot) => set((state) => ({
    snapshot,
    selectedExpiry: state.selectedExpiry ?? snapshot?.active_expiry ?? null,
  })),
  setChain: (chain) => set((state) => ({
    chain,
    snapshot: chain?.snapshot ?? state.snapshot,
    selectedExpiry: chain?.snapshot.active_expiry ?? state.selectedExpiry,
  })),
  setPortfolios: (portfolios) => set((state) => ({
    portfolios,
    selectedPortfolioId: portfolios.some((item) => item.id === state.selectedPortfolioId)
      ? state.selectedPortfolioId
      : (portfolios[0]?.id ?? 'manual'),
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
      selectedExpiry: chain.snapshot.active_expiry ?? state.selectedExpiry,
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
