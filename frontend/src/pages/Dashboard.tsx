import { useState } from 'react'
import { Ticket, X } from 'lucide-react'

import NiftyChart from '../components/NiftyChart'
import OptionsPanel from '../components/OptionsPanel'
import OrderTicket from '../components/OrderTicket'
import { useStore } from '../store/useStore'

export default function Dashboard() {
  const { snapshot } = useStore()
  const [showMobileTicket, setShowMobileTicket] = useState(false)

  return (
    <div className="flex h-full">
      {/* Left: Options Panel */}
      <OptionsPanel />

      {/* Center: Full-height Chart */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {snapshot?.degraded && (
          <div className="border-b border-loss/30 bg-loss/10 px-3 py-1.5 text-xs text-loss">
            Market data degraded: {snapshot.degraded_reason ?? 'unknown'}
          </div>
        )}
        <div className="flex-1 min-h-0">
          <NiftyChart />
        </div>
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
            <OrderTicket />
          </div>
        </div>
      )}
    </div>
  )
}
