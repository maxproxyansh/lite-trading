/** Enriched trade summary with market context fields.
 *  Matches the planned backend `DetailedTradeSummary` schema.
 *  Defined here to avoid duplication across analytics modules
 *  until the backend schema is generated. */
export type Trade = {
  symbol: string
  strike: number
  option_type: 'CE' | 'PE'
  direction: 'LONG' | 'SHORT'
  quantity: number
  lots: number
  entry_time: string
  exit_time: string
  hold_seconds: number
  hold_days: number
  realized_pnl: number
  entry_price: number
  exit_price: number
  expiry_date: string
  days_to_expiry_at_entry: number
  days_to_expiry_at_exit: number
  spot_at_entry: number | null
  spot_at_exit: number | null
  vix_at_entry: number | null
  vix_at_exit: number | null
  atm_distance: number | null
}

export type SliceRow = {
  label: string
  count: number
  wins: number
  winRate: number
  totalPnl: number
  avgPnl: number
}

export type BehavioralInsight = {
  label: string
  description: string
  value: string
  verdict: 'good' | 'bad' | 'neutral'
}
