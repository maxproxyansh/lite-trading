import type { Candle } from '../../api'

type SupertrendPoint = { time: number; value: number; direction: 'up' | 'down' }

export function computeSupertrend(candles: Candle[], period: number, multiplier: number): SupertrendPoint[] {
  if (candles.length < period) return []
  const tr: number[] = []
  for (let i = 0; i < candles.length; i++) {
    if (i === 0) { tr.push(candles[i].high - candles[i].low) }
    else { tr.push(Math.max(candles[i].high - candles[i].low, Math.abs(candles[i].high - candles[i - 1].close), Math.abs(candles[i].low - candles[i - 1].close))) }
  }
  const result: SupertrendPoint[] = []
  let atr = 0
  for (let i = 0; i < period; i++) atr += tr[i]
  atr /= period
  let upperBand = 0, lowerBand = 0, supertrend = 0
  let direction: 'up' | 'down' = 'up'
  for (let i = period; i < candles.length; i++) {
    atr = (atr * (period - 1) + tr[i]) / period
    const hl2 = (candles[i].high + candles[i].low) / 2
    const newUpper = hl2 + multiplier * atr
    const newLower = hl2 - multiplier * atr
    upperBand = newUpper < upperBand || candles[i - 1].close > upperBand ? newUpper : upperBand
    lowerBand = newLower > lowerBand || candles[i - 1].close < lowerBand ? newLower : lowerBand
    if (supertrend === upperBand) { direction = candles[i].close > upperBand ? 'up' : 'down' }
    else { direction = candles[i].close < lowerBand ? 'down' : 'up' }
    supertrend = direction === 'up' ? lowerBand : upperBand
    result.push({ time: candles[i].time, value: supertrend, direction })
  }
  return result
}
