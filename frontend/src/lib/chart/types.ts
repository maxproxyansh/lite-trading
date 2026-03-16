export type DrawingType = 'hline' | 'vline' | 'trendline' | 'channel' | 'rectangle' | 'fib' | 'measure'

export type DrawingPoint = {
  time: number   // IST-shifted UTC timestamp (raw_utc + IST_OFFSET_SECONDS)
  price: number
}

export type DrawingStyle = {
  color: string           // hex e.g. '#6366f1'
  lineWidth: 1 | 2 | 3 | 4
  lineStyle: 'solid' | 'dashed' | 'dotted'
  fillOpacity?: number    // 0-1, for rect/channel/fib zones
}

export type Drawing = {
  id: string              // crypto.randomUUID()
  type: DrawingType
  points: DrawingPoint[]
  style: DrawingStyle
  createdAt: number
}

export type IndicatorType = 'ema' | 'sma' | 'bb' | 'vwap' | 'supertrend' | 'ichimoku' | 'rsi' | 'macd' | 'adx'

export type IndicatorConfig = {
  id: string              // crypto.randomUUID()
  type: IndicatorType
  enabled: boolean
  params: Record<string, number>
  color: string
  lineWidth: 1 | 2
}

export const OVERLAY_INDICATORS: IndicatorType[] = ['ema', 'sma', 'bb', 'vwap', 'supertrend', 'ichimoku']
export const OSCILLATOR_INDICATORS: IndicatorType[] = ['rsi', 'macd', 'adx']

export const DEFAULT_DRAWING_STYLE: DrawingStyle = {
  color: '#ffffff',
  lineWidth: 1,
  lineStyle: 'solid',
  fillOpacity: 0.12,
}

export const CHANNEL_DEFAULT_STYLE: DrawingStyle = {
  color: '#e53935',
  lineWidth: 1,
  lineStyle: 'solid',
  fillOpacity: 0.12,
}

export const DEFAULT_INDICATOR_CONFIGS: IndicatorConfig[] = [
  { id: crypto.randomUUID(), type: 'ema', enabled: false, params: { period: 21 }, color: '#f59e0b', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'sma', enabled: false, params: { period: 50 }, color: '#8b5cf6', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'bb', enabled: false, params: { period: 20, stdDev: 2 }, color: '#6366f1', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'vwap', enabled: false, params: {}, color: '#ec4899', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'supertrend', enabled: false, params: { period: 10, multiplier: 3 }, color: '#4caf50', lineWidth: 2 },
  { id: crypto.randomUUID(), type: 'ichimoku', enabled: false, params: { tenkan: 9, kijun: 26, senkou: 52 }, color: '#06b6d4', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'rsi', enabled: false, params: { period: 14 }, color: '#f59e0b', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'macd', enabled: false, params: { fast: 12, slow: 26, signal: 9 }, color: '#6366f1', lineWidth: 1 },
  { id: crypto.randomUUID(), type: 'adx', enabled: false, params: { period: 14 }, color: '#06b6d4', lineWidth: 1 },
]
