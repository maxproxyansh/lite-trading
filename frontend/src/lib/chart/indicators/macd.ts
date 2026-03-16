import type { Candle } from '../../api'

type MACDPoint = { time: number; macd: number; signal: number; histogram: number }

export function computeMACD(candles: Candle[], fastPeriod: number, slowPeriod: number, signalPeriod: number): MACDPoint[] {
  if (candles.length < slowPeriod + signalPeriod) return []
  const kFast = 2 / (fastPeriod + 1), kSlow = 2 / (slowPeriod + 1), kSignal = 2 / (signalPeriod + 1)
  let fastEma = 0, slowEma = 0
  for (let i = 0; i < slowPeriod; i++) { if (i < fastPeriod) fastEma += candles[i].close; slowEma += candles[i].close }
  fastEma = fastEma / fastPeriod; slowEma = slowEma / slowPeriod
  for (let i = fastPeriod; i < slowPeriod; i++) { fastEma = candles[i].close * kFast + fastEma * (1 - kFast) }
  const macdValues: { time: number; macd: number }[] = []
  for (let i = slowPeriod; i < candles.length; i++) {
    fastEma = candles[i].close * kFast + fastEma * (1 - kFast)
    slowEma = candles[i].close * kSlow + slowEma * (1 - kSlow)
    macdValues.push({ time: candles[i].time, macd: fastEma - slowEma })
  }
  if (macdValues.length < signalPeriod) return []
  let signalEma = 0
  for (let i = 0; i < signalPeriod; i++) signalEma += macdValues[i].macd
  signalEma /= signalPeriod
  const result: MACDPoint[] = []
  for (let i = signalPeriod - 1; i < macdValues.length; i++) {
    if (i >= signalPeriod) signalEma = macdValues[i].macd * kSignal + signalEma * (1 - kSignal)
    result.push({ time: macdValues[i].time, macd: macdValues[i].macd, signal: signalEma, histogram: macdValues[i].macd - signalEma })
  }
  return result
}
