import type { Candle } from '../../api'

export function computeSMA(candles: Candle[], period: number): { time: number; value: number }[] {
  if (candles.length < period) return []
  const result: { time: number; value: number }[] = []
  let sum = 0
  for (let i = 0; i < period; i++) sum += candles[i].close
  result.push({ time: candles[period - 1].time, value: sum / period })
  for (let i = period; i < candles.length; i++) {
    sum += candles[i].close - candles[i - period].close
    result.push({ time: candles[i].time, value: sum / period })
  }
  return result
}
