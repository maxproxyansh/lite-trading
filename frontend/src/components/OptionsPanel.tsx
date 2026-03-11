import { ChevronLeft, ChevronRight, Maximize2, Minimize2 } from 'lucide-react'

import { useStore } from '../store/useStore'
import ExpiryTabs from './ExpiryTabs'
import ChainFilterTabs from './ChainFilterTabs'
import OptionsChainCollapsed from './OptionsChainCollapsed'
import OptionsChainExpanded from './OptionsChainExpanded'

export default function OptionsPanel() {
  const {
    chain, snapshot,
    chainView, setChainView,
    chainFilter,
    chainPanelOpen, setChainPanelOpen,
  } = useStore()

  // Collapse toggle button (always visible)
  if (!chainPanelOpen) {
    return (
      <div className="hidden md:flex shrink-0 items-start">
        <button
          onClick={() => setChainPanelOpen(true)}
          className="mt-2 flex h-8 w-5 items-center justify-center border border-border-primary bg-bg-secondary text-text-muted hover:text-text-primary hover:bg-bg-hover transition-colors"
          title="Show options chain"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    )
  }

  const rows = chain?.rows ?? []
  const atm = rows.find((r) => r.is_atm)?.strike ?? 0

  // Filter rows based on chainFilter
  const filteredRows = rows.filter((row) => {
    if (chainFilter === 'ALL') return true
    if (chainFilter === 'ATM') return Math.abs(row.strike - atm) <= 150
    if (chainFilter === 'ITM') return row.strike < atm
    if (chainFilter === 'OTM') return row.strike > atm
    return true
  })

  // oi_lakhs comes from backend runtime data, not OpenAPI schema
  const maxOI = Math.max(
    ...rows.flatMap((r) => [
      ((r.call as Record<string, unknown>).oi_lakhs as number) ?? 0,
      ((r.put as Record<string, unknown>).oi_lakhs as number) ?? 0,
    ]),
    1,
  )

  const panelWidth = chainView === 'collapsed' ? 240 : 420
  const isExpanded = chainView === 'expanded'

  return (
    <div
      className="hidden md:flex shrink-0 flex-col border-r border-border-primary bg-bg-secondary overflow-hidden animate-fade-in"
      style={{ width: panelWidth }}
    >
      {/* Panel header */}
      <div className="flex items-center justify-between border-b border-border-primary px-2 py-1">
        <div className="flex items-center gap-1">
          <span className="text-[11px] font-medium text-text-secondary">Options</span>
          {snapshot && snapshot.spot > 0 && (
            <span className="text-[10px] tabular-nums text-text-muted">
              {snapshot.spot.toLocaleString('en-IN', { maximumFractionDigits: 1 })}
            </span>
          )}
        </div>
        <div className="flex items-center gap-0.5">
          {/* View toggle */}
          <button
            onClick={() => setChainView(isExpanded ? 'collapsed' : 'expanded')}
            className="flex h-5 w-5 items-center justify-center text-text-muted hover:text-text-primary transition-colors"
            title={isExpanded ? 'Compact view' : 'Detailed view'}
          >
            {isExpanded ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
          </button>
          {/* Collapse panel */}
          <button
            onClick={() => setChainPanelOpen(false)}
            className="flex h-5 w-5 items-center justify-center text-text-muted hover:text-text-primary transition-colors"
            title="Hide options chain"
          >
            <ChevronLeft size={14} />
          </button>
        </div>
      </div>

      {/* Expiry tabs */}
      <div className="border-b border-border-secondary">
        <ExpiryTabs maxVisible={isExpanded ? 6 : 4} />
      </div>

      {/* Filter tabs */}
      <div className="border-b border-border-secondary">
        <ChainFilterTabs />
      </div>

      {/* Chain content */}
      {!chain || !snapshot ? (
        <div className="flex flex-1 items-center justify-center text-xs text-text-muted">
          Waiting for data…
        </div>
      ) : filteredRows.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center text-text-muted">
          <p className="text-xs">No strikes match filter</p>
        </div>
      ) : isExpanded ? (
        <OptionsChainExpanded rows={filteredRows} maxOI={maxOI} />
      ) : (
        <OptionsChainCollapsed rows={filteredRows} maxOI={maxOI} />
      )}
    </div>
  )
}
