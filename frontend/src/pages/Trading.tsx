import { useState } from 'react'

import History from './History'
import Orders from './Orders'
import Positions from './Positions'

type Tab = 'orders' | 'positions' | 'history'

export default function Trading() {
  const [tab, setTab] = useState<Tab>('positions')

  return (
    <div className="flex h-full flex-col">
      {/* Sub-tabs — mobile only */}
      <div className="flex border-b border-border-secondary md:hidden">
        <button
          onClick={() => setTab('orders')}
          className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors ${
            tab === 'orders'
              ? 'border-b-2 border-brand text-brand'
              : 'text-text-muted'
          }`}
        >
          Orders
        </button>
        <button
          onClick={() => setTab('positions')}
          className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors ${
            tab === 'positions'
              ? 'border-b-2 border-brand text-brand'
              : 'text-text-muted'
          }`}
        >
          Positions
        </button>
        <button
          onClick={() => setTab('history')}
          className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors ${
            tab === 'history'
              ? 'border-b-2 border-brand text-brand'
              : 'text-text-muted'
          }`}
        >
          History
        </button>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto">
        {tab === 'orders' && <Orders />}
        {tab === 'positions' && <Positions />}
        {tab === 'history' && <History />}
      </div>
    </div>
  )
}
