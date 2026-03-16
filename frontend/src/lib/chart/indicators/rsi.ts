import type { Candle } from '../../api'

export function computeRSI(candles: Candle[], period: number): { time: number; value: number }[] {
  if (candles.length < period + 1) return []
  const result: { time: number; value: number }[] = []
  let avgGain = 0, avgLoss = 0
  for (let i = 1; i <= period; i++) {
    const diff = candles[i].close - candles[i - 1].close
    if (diff > 0) avgGain += diff; else avgLoss -= diff
  }
  avgGain /= period; avgLoss /= period
  const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
  result.push({ time: candles[period].time, value: 100 - 100 / (1 + rs) })
  for (let i = period + 1; i < candles.length; i++) {
    const diff = candles[i].close - candles[i - 1].close
    const gain = diff > 0 ? diff : 0; const loss = diff < 0 ? -diff : 0
    avgGain = (avgGain * (period - 1) + gain) / period
    avgLoss = (avgLoss * (period - 1) + loss) / period
    const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
    result.push({ time: candles[i].time, value: rsi })
  }
  return result
}
