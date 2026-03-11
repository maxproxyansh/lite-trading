import { ChevronLeft, ChevronRight, Maximize2, Minimize2 } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'

import { useStore } from '../store/useStore'
import ChainFilterTabs from './ChainFilterTabs'
import ExpiryTabs from './ExpiryTabs'
import OptionsChainCollapsed from './OptionsChainCollapsed'
import OptionsChainExpanded from './OptionsChainExpanded'

export default function OptionsPanel() {
  const {
    chain,
    spot,
    chainView,
    setChainView,
    chainFilter,
    chainPanelOpen,
    setChainPanelOpen,
  } = useStore(useShallow((state) => ({
    chain: state.chain,
    spot: state.snapshot?.spot ?? null,
    chainView: state.chainView,
    setChainView: state.setChainView,
    chainFilter: state.chainFilter,
    chainPanelOpen: state.chainPanelOpen,
    setChainPanelOpen: state.setChainPanelOpen,
  })))

  if (!chainPanelOpen) {
    return (
      <div className="hidden shrink-0 items-start md:flex">
        <button
          onClick={() => setChainPanelOpen(true)}
          className="mt-2 flex h-8 w-5 items-center justify-center border border-border-primary bg-bg-secondary text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
          title="Show options chain"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    )
  }

  const rows = chain?.rows ?? []
  const atm = rows.find((row) => row.is_atm)?.strike ?? 0
  const filteredRows = rows.filter((row) => {
    if (chainFilter === 'ALL') {
      return true
    }
    if (chainFilter === 'ATM') {
      return Math.abs(row.strike - atm) <= 150
    }
    if (chainFilter === 'ITM') {
      return row.strike < atm
    }
    if (chainFilter === 'OTM') {
      return row.strike > atm
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

  const isExpanded = chainView === 'expanded'

  return (
    <div
      className="hidden shrink-0 flex-col overflow-hidden border-r border-border-primary bg-bg-secondary animate-fade-in md:flex"
      style={{ width: isExpanded ? 420 : 240 }}
    >
      <div className="flex items-center justify-between border-b border-border-primary px-2 py-1">
        <div className="flex items-center gap-1">
          <span className="text-[11px] font-medium text-text-secondary">Options</span>
          {spot && spot > 0 && (
            <span className="text-[10px] tabular-nums text-text-muted">
              {spot.toLocaleString('en-IN', { maximumFractionDigits: 1 })}
            </span>
          )}
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => setChainView(isExpanded ? 'collapsed' : 'expanded')}
            className="flex h-5 w-5 items-center justify-center text-text-muted transition-colors hover:text-text-primary"
            title={isExpanded ? 'Compact view' : 'Detailed view'}
          >
            {isExpanded ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
          </button>
          <button
            onClick={() => setChainPanelOpen(false)}
            className="flex h-5 w-5 items-center justify-center text-text-muted transition-colors hover:text-text-primary"
            title="Hide options chain"
          >
            <ChevronLeft size={14} />
          </button>
        </div>
      </div>

      <div className="border-b border-border-secondary">
        <ExpiryTabs maxVisible={isExpanded ? 6 : 4} />
      </div>

      <div className="border-b border-border-secondary">
        <ChainFilterTabs />
      </div>

      {!chain ? (
        <div className="flex flex-1 items-center justify-center text-xs text-text-muted">
          Waiting for data…
        </div>
      ) : filteredRows.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center text-text-muted">
          <p className="text-xs">No strikes match filter</p>
        </div>
      ) : isExpanded ? (
        <OptionsChainExpanded
          rows={filteredRows}
          maxOI={maxOI}
          activeExpiry={chain.snapshot.active_expiry ?? null}
        />
      ) : (
        <OptionsChainCollapsed
          rows={filteredRows}
          maxOI={maxOI}
          activeExpiry={chain.snapshot.active_expiry ?? null}
        />
      )}
    </div>
  )
}
