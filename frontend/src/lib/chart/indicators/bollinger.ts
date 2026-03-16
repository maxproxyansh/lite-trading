import type { Candle } from '../../api'

type BollingerPoint = { time: number; middle: number; upper: number; lower: number }

export function computeBollinger(candles: Candle[], period: number, stdDev: number): BollingerPoint[] {
  if (candles.length < period) return []
  const result: BollingerPoint[] = []
  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) sum += candles[j].close
    const mean = sum / period
    let sqSum = 0
    for (let j = i - period + 1; j <= i; j++) sqSum += (candles[j].close - mean) ** 2
    const sd = Math.sqrt(sqSum / period)
    result.push({ time: candles[i].time, middle: mean, upper: mean + stdDev * sd, lower: mean - stdDev * sd })
  }
  return result
}
