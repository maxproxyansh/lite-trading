import { useState } from 'react'
import { Ticket, X } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'

import NiftyChart from '../components/NiftyChart'
import OptionsPanel from '../components/OptionsPanel'
import OrderTicket from '../components/OrderTicket'
import { useStore } from '../store/useStore'

export default function Dashboard() {
  const { degraded, degradedReason } = useStore(useShallow((state) => ({
    degraded: state.snapshot?.degraded ?? false,
    degradedReason: state.snapshot?.degraded_reason ?? null,
  })))
  const [showMobileTicket, setShowMobileTicket] = useState(false)

  return (
    <div className="flex h-full">
      <OptionsPanel />

      <div className="flex flex-1 flex-col overflow-hidden">
        {degraded && (
          <div className="border-b border-loss/30 bg-loss/10 px-3 py-1.5 text-xs text-loss">
            Market data degraded: {degradedReason ?? 'unknown'}
          </div>
        )}
        <div className="flex-1 min-h-0">
          <NiftyChart />
        </div>
      </div>

      <button
        onClick={() => setShowMobileTicket(true)}
        className="fixed bottom-16 right-4 z-20 flex h-12 w-12 items-center justify-center rounded-full bg-signal text-white shadow-lg md:hidden"
      >
        <Ticket size={20} />
      </button>

      {showMobileTicket && (
        <div className="fixed inset-0 z-40 bg-black/60 md:hidden" onClick={() => setShowMobileTicket(false)}>
          <div
            className="absolute bottom-0 left-0 right-0 max-h-[80vh] overflow-auto rounded-t-lg bg-bg-secondary p-4"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between">
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
