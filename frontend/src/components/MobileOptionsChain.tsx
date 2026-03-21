import { useShallow } from 'zustand/react/shallow'

import { resolveAtmStrike } from '../lib/options'
import { useStore } from '../store/useStore'
import ChainFilterTabs from './ChainFilterTabs'
import ExpiryTabs from './ExpiryTabs'
import OptionsChainCollapsed from './OptionsChainCollapsed'

export default function MobileOptionsChain() {
  const { chain, spot, chainFilter } = useStore(useShallow((state) => ({
    chain: state.chain,
    spot: state.snapshot?.spot ?? null,
    chainFilter: state.chainFilter,
  })))

  const rows = chain?.rows ?? []
  const atmStrike = resolveAtmStrike(rows, spot)
  const filteredRows = rows.filter((row) => {
    if (chainFilter === 'ALL') {
      return true
    }
    if (atmStrike == null) {
      return true
    }
    if (chainFilter === 'ATM') {
      return Math.abs(row.strike - atmStrike) <= 300
    }
    if (chainFilter === 'ITM') {
      return row.strike < atmStrike
    }
    if (chainFilter === 'OTM') {
      return row.strike > atmStrike
    }
    return true
  })
  const maxOI = Math.max(
    ...rows.flatMap((row) => [
      ((row.call as Record<string, unknown>).oi_lakhs as number) ?? 0,
      ((row.put as Record<string, unknown>).oi_lakhs as number) ?? 0,
    ]),
    1,
  )

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Spot price bar */}
      <div className="flex items-center justify-between border-b border-border-secondary px-3 py-1.5">
        <span className="text-[11px] font-medium text-text-secondary">Options Chain</span>
        {spot && spot > 0 && (
          <span className="text-[11px] tabular-nums font-medium text-text-primary">
            {spot.toLocaleString('en-IN', { maximumFractionDigits: 1 })}
          </span>
        )}
      </div>

      {/* Expiry tabs */}
      <div className="border-b border-border-secondary">
        <ExpiryTabs maxVisible={4} />
      </div>

      {/* Filter tabs */}
      <div className="border-b border-border-secondary">
        <ChainFilterTabs />
      </div>

      {/* Chain content */}
      {!chain ? (
        <div className="flex flex-1 items-center justify-center text-xs text-text-muted">
          Waiting for data…
        </div>
      ) : filteredRows.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-xs text-text-muted">
          No strikes match filter
        </div>
      ) : (
        <OptionsChainCollapsed
          rows={filteredRows}
          maxOI={maxOI}
          atmStrike={atmStrike}
          activeExpiry={chain.snapshot.active_expiry ?? null}
        />
      )}
    </div>
  )
}
