import type { Trade, SliceRow } from './types'

export type { SliceRow }

export function sliceTrades(
  trades: Trade[],
  labelFn: (t: Trade) => string,
): SliceRow[] {
  const buckets = new Map<string, Trade[]>()
  for (const t of trades) {
    const key = labelFn(t)
    const arr = buckets.get(key) ?? []
    arr.push(t)
    buckets.set(key, arr)
  }
  const result: SliceRow[] = []
  for (const [label, group] of buckets) {
    const wins = group.filter((t) => t.realized_pnl > 0).length
    const totalPnl = group.reduce((s, t) => s + t.realized_pnl, 0)
    result.push({
      label,
      count: group.length,
      wins,
      winRate: group.length ? Math.round((wins / group.length) * 100 * 10) / 10 : 0,
      totalPnl: Math.round(totalPnl * 100) / 100,
      avgPnl: group.length ? Math.round((totalPnl / group.length) * 100) / 100 : 0,
    })
  }
  return result.sort((a, b) => b.totalPnl - a.totalPnl)
}

// ── Basic attribution ──

export const sliceByOptionType = (trades: Trade[]) =>
  sliceTrades(trades, (t) => t.option_type)

export const sliceByDirection = (trades: Trade[]) =>
  sliceTrades(trades, (t) => t.direction)

// ── Moneyness (ATM +/-50pts) ──

export const sliceByMoneyness = (trades: Trade[]) =>
  sliceTrades(trades, (t) => {
    if (t.atm_distance == null) return 'Unknown'
    const d = Math.abs(t.atm_distance)
    if (d <= 50) return 'ATM'
    const isOtm =
      (t.option_type === 'CE' && t.atm_distance > 0) ||
      (t.option_type === 'PE' && t.atm_distance < 0)
    return isOtm ? 'OTM' : 'ITM'
  })

// ── Hold duration ──

export const sliceByHoldDuration = (trades: Trade[]) =>
  sliceTrades(trades, (t) => {
    if (t.hold_days === 0) return 'Intraday'
    if (t.hold_days <= 2) return '1-2 days'
    if (t.hold_days <= 7) return '3-7 days'
    return '7+ days'
  })

// ── Days to expiry at entry ──

export const sliceByDTE = (trades: Trade[]) =>
  sliceTrades(trades, (t) => {
    if (t.days_to_expiry_at_entry === 0) return 'Expiry day'
    if (t.days_to_expiry_at_entry <= 2) return '1-2 days out'
    if (t.days_to_expiry_at_entry <= 5) return '3-5 days out'
    return '5+ days out'
  })

// ── Position size ──

export const sliceBySize = (trades: Trade[]) =>
  sliceTrades(trades, (t) => {
    if (t.lots === 1) return '1 lot'
    if (t.lots === 2) return '2 lots'
    return '3+ lots'
  })

// ── VIX regime at entry ──

export const sliceByVixRegime = (trades: Trade[]) =>
  sliceTrades(trades, (t) => {
    if (t.vix_at_entry == null) return 'Unknown'
    if (t.vix_at_entry < 13) return 'Low VIX (<13)'
    if (t.vix_at_entry < 18) return 'Normal VIX (13-18)'
    return 'High VIX (>18)'
  })

// ── VIX change during trade ──

export const sliceByVixChange = (trades: Trade[]) =>
  sliceTrades(trades, (t) => {
    if (t.vix_at_entry == null || t.vix_at_exit == null) return 'Unknown'
    const delta = t.vix_at_exit - t.vix_at_entry
    if (delta < -1) return 'VIX fell (>1pt)'
    if (delta > 1) return 'VIX rose (>1pt)'
    return 'VIX flat'
  })

// ── Spot move during trade ──

export const sliceBySpotMove = (trades: Trade[]) =>
  sliceTrades(trades, (t) => {
    if (t.spot_at_entry == null || t.spot_at_exit == null) return 'Unknown'
    const move = Math.abs(t.spot_at_exit - t.spot_at_entry)
    if (move < 50) return 'Nifty <50pts'
    if (move < 100) return 'Nifty 50-100pts'
    if (move < 200) return 'Nifty 100-200pts'
    return 'Nifty 200+pts'
  })

// ── Day of week ──

export const sliceByDayOfWeek = (trades: Trade[]) =>
  sliceTrades(
    trades,
    (t) => ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][new Date(t.entry_time).getDay()],
  )

// ── Time of day ──

export const sliceByTimeOfDay = (trades: Trade[]) =>
  sliceTrades(trades, (t) => {
    const d = new Date(t.entry_time)
    const mins = d.getHours() * 60 + d.getMinutes()
    if (mins < 600) return 'Pre-10:00'
    if (mins < 690) return 'Morning 10-11:30'
    if (mins < 810) return 'Midday 11:30-13:30'
    return 'Afternoon 13:30+'
  })

// ── Expiry week (<=4 DTE = expiry week) ──

export const sliceByExpiryWeek = (trades: Trade[]) =>
  sliceTrades(trades, (t) =>
    t.days_to_expiry_at_entry <= 4 ? 'Expiry week' : 'Non-expiry week',
  )
