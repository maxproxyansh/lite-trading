import type { components } from './api-schema'
import { useStore } from '../store/useStore'

export type UserSummary = components['schemas']['UserSummary']
export type TokenEnvelope = components['schemas']['TokenEnvelope']
export type MarketSnapshot = components['schemas']['MarketSnapshot']
export type OptionQuote = components['schemas']['OptionQuote']
export type OptionChainRow = components['schemas']['OptionChainRow']
export type OptionChainResponse = components['schemas']['OptionChainResponse']
export type Candle = components['schemas']['Candle']
export type CandleResponse = components['schemas']['CandleResponse']
export type AlertSummary = components['schemas']['AlertSummary']
export type AlertPayload = components['schemas']['AlertCreateRequest']
export type PortfolioSummary = components['schemas']['PortfolioSummary']
export type OrderSummary = components['schemas']['OrderSummary']
export type PositionSummary = components['schemas']['PositionSummary']
export type FundsResponse = components['schemas']['FundsResponse']
export type SignalResponse = components['schemas']['SignalResponse']
export type AnalyticsPoint = components['schemas']['AnalyticsPoint']
export type AnalyticsResponse = components['schemas']['AnalyticsResponse']
export type OrderPayload = components['schemas']['OrderRequest']
export type CreateAgentKeyPayload = components['schemas']['CreateAgentKeyRequest']
export type AgentKeyResponse = components['schemas']['AgentKeyResponse']
export type CreateUserPayload = components['schemas']['CreateUserRequest']
export type QuotePatch = Partial<OptionQuote> & Pick<OptionQuote, 'symbol'> & { oi_lakhs?: number | null }
export type QuoteBatchEvent = {
  active_expiry: string | null
  updated_at: string
  quotes: QuotePatch[]
}
export type PortfolioRefreshEvent = {
  portfolio_id?: string | null
  reason?: string | null
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const REQUEST_TIMEOUT_MS = 15000

export class ApiError extends Error {
  status: number
  kind: 'network' | 'auth' | 'server'

  constructor(message: string, status: number, kind: ApiError['kind']) {
    super(message)
    this.status = status
    this.kind = kind
  }
}

function getAccessToken() {
  return useStore.getState().accessToken
}

function setSession(token: string | null, user: UserSummary | null) {
  useStore.getState().setSession(token, user)
}

function readCookie(name: string) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

async function rawFetch<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getAccessToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const csrfToken = readCookie('lite_csrf')
  if (csrfToken && !headers.has('X-CSRF-Token') && (init.method ?? 'GET').toUpperCase() !== 'GET') {
    headers.set('X-CSRF-Token', csrfToken)
  }
  if (!(init.body instanceof FormData) && !headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json')
  }

  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: 'include',
      signal: controller.signal,
    })
  } catch (error) {
    window.clearTimeout(timer)
    throw new ApiError(
      error instanceof DOMException && error.name === 'AbortError' ? 'Request timed out' : 'Network error',
      0,
      'network',
    )
  }
  window.clearTimeout(timer)

  if (response.status === 401 && retry && !path.includes('/auth/')) {
    const refreshed = await refreshSession()
    if (refreshed) {
      return rawFetch<T>(path, init, false)
    }
  }

  if (!response.ok) {
    const errorText = await response.text()
    throw new ApiError(
      errorText || response.statusText,
      response.status,
      response.status === 401 ? 'auth' : response.status >= 500 ? 'server' : 'network',
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export async function login(email: string, password: string) {
  const envelope = await rawFetch<TokenEnvelope>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }, false)
  setSession(envelope.access_token, envelope.user)
  return envelope
}

export async function signup(email: string, displayName: string, password: string) {
  const envelope = await rawFetch<TokenEnvelope>('/api/v1/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, display_name: displayName, password }),
  }, false)
  setSession(envelope.access_token, envelope.user)
  return envelope
}

export async function refreshSession() {
  try {
    const envelope = await rawFetch<TokenEnvelope>('/api/v1/auth/refresh', { method: 'POST' }, false)
    setSession(envelope.access_token, envelope.user)
    return true
  } catch {
    setSession(null, null)
    return false
  }
}

export async function logout() {
  try {
    await rawFetch('/api/v1/auth/logout', { method: 'POST' }, false)
  } finally {
    setSession(null, null)
  }
}

export async function fetchMe() {
  return rawFetch<UserSummary>('/api/v1/auth/me')
}

export async function fetchPortfolios() {
  return rawFetch<PortfolioSummary[]>('/api/v1/portfolios')
}

export async function fetchSnapshot() {
  return rawFetch<MarketSnapshot>('/api/v1/market/snapshot')
}

export async function fetchOptionChain(expiry?: string) {
  const qs = expiry ? `?expiry=${encodeURIComponent(expiry)}` : ''
  return rawFetch<OptionChainResponse>(`/api/v1/market/chain${qs}`)
}

export async function fetchCandles(timeframe: string, before?: number | null) {
  const params = new URLSearchParams({ timeframe })
  if (before !== undefined && before !== null) {
    params.set('before', String(before))
  }
  return rawFetch<CandleResponse>(`/api/v1/market/candles?${params.toString()}`)
}

export async function fetchAlerts() {
  return rawFetch<AlertSummary[]>('/api/v1/alerts')
}

export async function createAlert(payload: AlertPayload) {
  return rawFetch<AlertSummary>('/api/v1/alerts', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteAlert(alertId: string) {
  return rawFetch<void>(`/api/v1/alerts/${encodeURIComponent(alertId)}`, {
    method: 'DELETE',
  })
}

export async function fetchOrders(portfolioId?: string) {
  const qs = portfolioId ? `?portfolio_id=${encodeURIComponent(portfolioId)}` : ''
  return rawFetch<OrderSummary[]>(`/api/v1/orders${qs}`)
}

export async function fetchPositions(portfolioId?: string) {
  const qs = portfolioId ? `?portfolio_id=${encodeURIComponent(portfolioId)}` : ''
  return rawFetch<PositionSummary[]>(`/api/v1/positions${qs}`)
}

export async function fetchFunds(portfolioId: string) {
  return rawFetch<FundsResponse>(`/api/v1/funds?portfolio_id=${encodeURIComponent(portfolioId)}`)
}

export async function fetchAnalytics(portfolioId: string) {
  return rawFetch<AnalyticsResponse>(`/api/v1/analytics?portfolio_id=${encodeURIComponent(portfolioId)}`)
}

export async function fetchSignals() {
  return rawFetch<SignalResponse[]>('/api/v1/signals')
}

export async function fetchLatestSignal() {
  return rawFetch<SignalResponse | null>('/api/v1/signals/latest')
}

export async function submitOrder(payload: OrderPayload) {
  return rawFetch<OrderSummary>('/api/v1/orders', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function closePosition(positionId: string) {
  return rawFetch<PositionSummary>(`/api/v1/positions/${encodeURIComponent(positionId)}/close`, {
    method: 'POST',
  })
}

export async function createAgentKey(name: string, portfolioId: string, scopes: string[]) {
  return rawFetch<AgentKeyResponse>(
    '/api/v1/auth/api-keys',
    { method: 'POST', body: JSON.stringify({ name, portfolio_id: portfolioId, scopes }) },
  )
}

export async function createUser(payload: CreateUserPayload) {
  return rawFetch<UserSummary>('/api/v1/admin/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
