import { useState } from 'react'
import { Ticket, X } from 'lucide-react'

import NiftyChart from '../components/NiftyChart'
import OptionsChain from '../components/OptionsChain'
import OrderTicket from '../components/OrderTicket'
import SignalPanel from '../components/SignalPanel'
import { useStore } from '../store/useStore'

function DepthCard() {
  const { selectedQuote } = useStore()

  return (
    <div className="border-b border-border-primary p-3">
      <div className="mb-2 text-xs font-medium text-text-secondary">Market Depth</div>
      {selectedQuote ? (
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
      ) : (
        <div className="text-xs text-text-muted">Select a contract to view depth</div>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { snapshot } = useStore()
  const [showMobileTicket, setShowMobileTicket] = useState(false)

  return (
    <div className="flex h-full">
      {/* Center: Chart + Options Chain */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="h-[42%] shrink-0 border-b border-border-primary">
          <NiftyChart />
        </div>
        <div className="flex-1 overflow-auto">
          <OptionsChain />
        </div>
      </div>

      {/* Right Panel — hidden on mobile */}
      <div className="hidden md:flex md:w-[300px] md:shrink-0 md:flex-col overflow-auto border-l border-border-primary">
        {snapshot?.degraded && (
          <div className="border-b border-loss/30 bg-loss/10 px-3 py-2 text-xs text-loss">
            Market data degraded: {snapshot.degraded_reason ?? 'unknown'}
          </div>
        )}
        <SignalPanel />
        <DepthCard />
        <OrderTicket />
      </div>

      {/* Mobile floating ticket button */}
      <button
        onClick={() => setShowMobileTicket(true)}
        className="fixed bottom-16 right-4 md:hidden z-20 h-12 w-12 rounded-full bg-signal text-white shadow-lg flex items-center justify-center"
      >
        <Ticket size={20} />
      </button>

      {/* Mobile order overlay */}
      {showMobileTicket && (
        <div className="fixed inset-0 z-40 md:hidden bg-black/60" onClick={() => setShowMobileTicket(false)}>
          <div
            className="absolute bottom-0 left-0 right-0 bg-bg-secondary rounded-t-lg p-4 max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-text-secondary">Order Ticket</span>
              <button onClick={() => setShowMobileTicket(false)} className="text-text-muted">
                <X size={16} />
              </button>
            </div>
            <SignalPanel />
            <OrderTicket />
          </div>
        </div>
      )}
    </div>
  )
}
