import type { Candle } from '../../api'

export function computeVWAP(candles: Candle[]): { time: number; value: number }[] {
  if (candles.length === 0) return []
  const result: { time: number; value: number }[] = []
  let cumVol = 0
  let cumTPV = 0
  let lastDay = -1
  for (const candle of candles) {
    const day = Math.floor(candle.time / 86400)
    if (day !== lastDay) { cumVol = 0; cumTPV = 0; lastDay = day }
    const tp = (candle.high + candle.low + candle.close) / 3
    cumVol += candle.volume
    cumTPV += tp * candle.volume
    if (cumVol > 0) result.push({ time: candle.time, value: cumTPV / cumVol })
  }
  return result
}
