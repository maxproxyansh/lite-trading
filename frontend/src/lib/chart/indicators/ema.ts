import type { Candle } from '../../api'

export function computeEMA(candles: Candle[], period: number): { time: number; value: number }[] {
  if (candles.length < period) return []
  const k = 2 / (period + 1)
  const result: { time: number; value: number }[] = []
  let sum = 0
  for (let i = 0; i < period; i++) sum += candles[i].close
  let ema = sum / period
  result.push({ time: candles[period - 1].time, value: ema })
  for (let i = period; i < candles.length; i++) {
    ema = candles[i].close * k + ema * (1 - k)
    result.push({ time: candles[i].time, value: ema })
  }
  return result
}
