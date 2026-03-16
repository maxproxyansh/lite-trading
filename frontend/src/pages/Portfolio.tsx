import { useState } from 'react'
import Funds from './Funds'
import Analytics from './Analytics'

type Tab = 'funds' | 'analytics'

export default function Portfolio() {
  const [tab, setTab] = useState<Tab>('funds')

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-border-secondary md:hidden">
        <button
          onClick={() => setTab('funds')}
          className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors ${
            tab === 'funds'
              ? 'border-b-2 border-brand text-brand'
              : 'text-text-muted'
          }`}
        >
          Funds
        </button>
        <button
          onClick={() => setTab('analytics')}
          className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors ${
            tab === 'analytics'
              ? 'border-b-2 border-brand text-brand'
              : 'text-text-muted'
          }`}
        >
          Analytics
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        {tab === 'funds' ? <Funds /> : <Analytics />}
      </div>
    </div>
  )
}
