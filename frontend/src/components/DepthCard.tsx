import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

import { useStore } from '../store/useStore'

export default function DepthCard() {
  const { selectedQuote } = useStore()
  const [expanded, setExpanded] = useState(false)

  if (!selectedQuote) return null

  return (
    <div className="border-b border-border-primary">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs text-text-muted hover:bg-bg-hover transition-colors"
      >
        <span>Market Depth</span>
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {expanded && (
        <div className="px-3 pb-3 animate-fade-in">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded bg-bg-primary p-2">
              <div className="text-[10px] text-text-muted">Bid</div>
              <div className="mt-0.5 tabular-nums text-text-primary">{selectedQuote.bid?.toFixed(2) ?? '--'}</div>
              <div className="text-[10px] tabular-nums text-text-muted">Qty {selectedQuote.bid_qty ?? '--'}</div>
            </div>
            <div className="rounded bg-bg-primary p-2">
              <div className="text-[10px] text-text-muted">Ask</div>
              <div className="mt-0.5 tabular-nums text-text-primary">{selectedQuote.ask?.toFixed(2) ?? '--'}</div>
              <div className="text-[10px] tabular-nums text-text-muted">Qty {selectedQuote.ask_qty ?? '--'}</div>
            </div>
            <div className="rounded bg-bg-primary p-2">
              <div className="text-[10px] text-text-muted">IV</div>
              <div className="mt-0.5 tabular-nums text-text-primary">{selectedQuote.iv?.toFixed(2) ?? '--'}</div>
            </div>
            <div className="rounded bg-bg-primary p-2">
              <div className="text-[10px] text-text-muted">Greeks</div>
              <div className="mt-0.5 tabular-nums text-text-primary">
                &Delta; {selectedQuote.delta?.toFixed(2) ?? '--'} &Gamma; {selectedQuote.gamma?.toFixed(3) ?? '--'}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
