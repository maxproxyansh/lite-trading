import type { Candle } from '../../api'

type IchimokuPoint = { time: number; tenkan: number | null; kijun: number | null; senkouA: number | null; senkouB: number | null; chikou: number | null }

function highLow(candles: Candle[], end: number, period: number): { high: number; low: number } | null {
  const start = end - period + 1
  if (start < 0) return null
  let high = -Infinity, low = Infinity
  for (let i = start; i <= end; i++) { if (candles[i].high > high) high = candles[i].high; if (candles[i].low < low) low = candles[i].low }
  return { high, low }
}

export function computeIchimoku(candles: Candle[], tenkanPeriod: number, kijunPeriod: number, senkouPeriod: number): IchimokuPoint[] {
  const result: IchimokuPoint[] = []
  for (let i = 0; i < candles.length; i++) {
    const tenkanHL = highLow(candles, i, tenkanPeriod)
    const kijunHL = highLow(candles, i, kijunPeriod)
    const senkouBHL = highLow(candles, i, senkouPeriod)
    const tenkan = tenkanHL ? (tenkanHL.high + tenkanHL.low) / 2 : null
    const kijun = kijunHL ? (kijunHL.high + kijunHL.low) / 2 : null
    const senkouA = tenkan !== null && kijun !== null ? (tenkan + kijun) / 2 : null
    const senkouB = senkouBHL ? (senkouBHL.high + senkouBHL.low) / 2 : null
    const chikou = candles[i].close
    result.push({ time: candles[i].time, tenkan, kijun, senkouA, senkouB, chikou })
  }
  return result
}
