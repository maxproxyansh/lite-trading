import type { OptionChainRow } from './api'

export function roundSpotToAtmStrike(spot: number | null | undefined): number | null {
  if (spot == null || spot <= 0) {
    return null
  }
  return Math.floor((spot + 25) / 50) * 50
}

export function resolveAtmStrike(rows: OptionChainRow[], spot: number | null | undefined): number | null {
  return roundSpotToAtmStrike(spot) ?? rows.find((row) => row.is_atm)?.strike ?? null
}
