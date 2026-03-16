import type { Trade, BehavioralInsight } from './types'

export type { BehavioralInsight }

function fmtCurrency(v: number): string {
  const sign = v >= 0 ? '+' : '-'
  return `${sign}\u20B9${Math.abs(v).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

/**
 * Revenge trading: entry within 30min of a losing trade's exit.
 * Returns stats on revenge trades vs normal trades.
 */
export function detectRevengeTrades(trades: Trade[]): BehavioralInsight | null {
  const sorted = [...trades].sort(
    (a, b) => new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime(),
  )
  let revengeCount = 0
  let revengeWins = 0
  let revengePnl = 0

  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1]
    const curr = sorted[i]
    if (prev.realized_pnl >= 0) continue // previous wasn't a loss
    const gap =
      (new Date(curr.entry_time).getTime() - new Date(prev.exit_time).getTime()) / 60000
    if (gap <= 30 && gap >= 0) {
      revengeCount++
      if (curr.realized_pnl > 0) revengeWins++
      revengePnl += curr.realized_pnl
    }
  }

  if (revengeCount === 0) return null
  const wr = Math.round((revengeWins / revengeCount) * 100)
  return {
    label: 'Revenge Trading',
    description: `${revengeCount} trades entered within 30min of a loss`,
    value: `${wr}% win rate, ${fmtCurrency(revengePnl)} P&L`,
    verdict: wr < 40 ? 'bad' : 'neutral',
  }
}

/**
 * Overtrading: days with 3+ trades vs 1-2 trades.
 * Compares avg daily P&L.
 */
export function detectOvertrading(trades: Trade[]): BehavioralInsight | null {
  const byDay = new Map<string, Trade[]>()
  for (const t of trades) {
    const day = new Date(t.entry_time).toISOString().slice(0, 10)
    byDay.set(day, [...(byDay.get(day) ?? []), t])
  }

  let heavyDays = 0
  let heavyPnl = 0
  let lightDays = 0
  let lightPnl = 0
  for (const [, dayTrades] of byDay) {
    const pnl = dayTrades.reduce((s, t) => s + t.realized_pnl, 0)
    if (dayTrades.length >= 3) {
      heavyDays++
      heavyPnl += pnl
    } else {
      lightDays++
      lightPnl += pnl
    }
  }

  if (heavyDays === 0 || lightDays === 0) return null
  const heavyAvg = heavyPnl / heavyDays
  const lightAvg = lightPnl / lightDays
  return {
    label: 'Overtrading',
    description: `${heavyDays} days with 3+ trades vs ${lightDays} days with 1-2`,
    value: `Heavy: \u20B9${Math.abs(heavyAvg).toLocaleString('en-IN', { maximumFractionDigits: 0 })}/day, Light: \u20B9${Math.abs(lightAvg).toLocaleString('en-IN', { maximumFractionDigits: 0 })}/day`,
    verdict: heavyAvg < lightAvg ? 'bad' : 'neutral',
  }
}

/**
 * Conviction sizing: do larger trades (2+ lots) win more?
 */
export function analyzeConvictionSizing(trades: Trade[]): BehavioralInsight | null {
  const big = trades.filter((t) => t.lots >= 2)
  const small = trades.filter((t) => t.lots === 1)
  if (big.length < 2 || small.length < 2) return null

  const bigWR = Math.round((big.filter((t) => t.realized_pnl > 0).length / big.length) * 100)
  const smallWR = Math.round(
    (small.filter((t) => t.realized_pnl > 0).length / small.length) * 100,
  )
  return {
    label: 'Conviction Sizing',
    description: `${big.length} trades at 2+ lots vs ${small.length} at 1 lot`,
    value: `Big: ${bigWR}% win rate, Small: ${smallWR}% win rate`,
    verdict: bigWR > smallWR ? 'good' : bigWR < smallWR - 10 ? 'bad' : 'neutral',
  }
}

/**
 * Premium capture: what % of entry premium was captured.
 */
export function analyzePremiumCapture(trades: Trade[]): BehavioralInsight | null {
  const withPrices = trades.filter((t) => t.entry_price > 0 && t.exit_price >= 0)
  if (withPrices.length === 0) return null

  const captures = withPrices.map((t) => {
    if (t.direction === 'SHORT') return ((t.entry_price - t.exit_price) / t.entry_price) * 100
    return ((t.exit_price - t.entry_price) / t.entry_price) * 100
  })
  const avg = captures.reduce((s, v) => s + v, 0) / captures.length
  return {
    label: 'Premium Capture',
    description: 'Avg % of entry premium captured per trade',
    value: `${avg >= 0 ? '+' : ''}${avg.toFixed(1)}%`,
    verdict: avg > 0 ? 'good' : 'bad',
  }
}

/**
 * Gap risk: for overnight holds, was the opening gap helpful or harmful?
 * Approximated by comparing spot_at_exit to spot_at_entry for multi-day trades.
 */
export function analyzeGapRisk(trades: Trade[]): BehavioralInsight | null {
  const overnight = trades.filter(
    (t) => t.hold_days >= 1 && t.spot_at_entry != null && t.spot_at_exit != null,
  )
  if (overnight.length < 2) return null

  const gapHelped = overnight.filter((t) => {
    const spotMove = t.spot_at_exit! - t.spot_at_entry!
    // For long calls / short puts, spot up = good. For short calls / long puts, spot down = good.
    const wantsUp =
      (t.option_type === 'CE' && t.direction === 'LONG') ||
      (t.option_type === 'PE' && t.direction === 'SHORT')
    return wantsUp ? spotMove > 0 : spotMove < 0
  }).length

  const pct = Math.round((gapHelped / overnight.length) * 100)
  const overnightPnl = overnight.reduce((s, t) => s + t.realized_pnl, 0)
  return {
    label: 'Overnight Gap Exposure',
    description: `${overnight.length} trades held overnight`,
    value: `Gap helped ${pct}% of the time, total P&L: ${fmtCurrency(overnightPnl)}`,
    verdict: pct > 55 ? 'good' : pct < 45 ? 'bad' : 'neutral',
  }
}
