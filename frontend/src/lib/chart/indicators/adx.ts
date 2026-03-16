import type { Candle } from '../../api'

type ADXPoint = { time: number; adx: number; plusDI: number; minusDI: number }

export function computeADX(candles: Candle[], period: number): ADXPoint[] {
  if (candles.length < period * 2 + 1) return []
  const tr: number[] = [], plusDM: number[] = [], minusDM: number[] = []
  for (let i = 1; i < candles.length; i++) {
    const highDiff = candles[i].high - candles[i - 1].high
    const lowDiff = candles[i - 1].low - candles[i].low
    tr.push(Math.max(candles[i].high - candles[i].low, Math.abs(candles[i].high - candles[i - 1].close), Math.abs(candles[i].low - candles[i - 1].close)))
    plusDM.push(highDiff > lowDiff && highDiff > 0 ? highDiff : 0)
    minusDM.push(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0)
  }
  let smoothTR = 0, smoothPlusDM = 0, smoothMinusDM = 0
  for (let i = 0; i < period; i++) { smoothTR += tr[i]; smoothPlusDM += plusDM[i]; smoothMinusDM += minusDM[i] }
  const dxValues: number[] = []
  const result: ADXPoint[] = []
  for (let i = period; i < tr.length; i++) {
    smoothTR = smoothTR - smoothTR / period + tr[i]
    smoothPlusDM = smoothPlusDM - smoothPlusDM / period + plusDM[i]
    smoothMinusDM = smoothMinusDM - smoothMinusDM / period + minusDM[i]
    const pdi = smoothTR === 0 ? 0 : (smoothPlusDM / smoothTR) * 100
    const mdi = smoothTR === 0 ? 0 : (smoothMinusDM / smoothTR) * 100
    const dx = pdi + mdi === 0 ? 0 : (Math.abs(pdi - mdi) / (pdi + mdi)) * 100
    dxValues.push(dx)
    if (dxValues.length >= period) {
      let adx: number
      if (dxValues.length === period) { adx = 0; for (let j = 0; j < period; j++) adx += dxValues[j]; adx /= period }
      else { const prevAdx = result[result.length - 1].adx; adx = (prevAdx * (period - 1) + dx) / period }
      result.push({ time: candles[i + 1].time, adx, plusDI: pdi, minusDI: mdi })
    }
  }
  return result
}
