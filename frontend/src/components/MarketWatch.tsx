import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'

import { useStore } from '../store/useStore'

export default function MarketWatch() {
  const [query, setQuery] = useState('')
  const { chain, selectedQuote, setSelectedQuote, snapshot } = useStore()

  const quotes = useMemo(() => {
    if (!chain) return []
    const flattened = chain.rows.flatMap((row) => [row.call, row.put])
    if (!query.trim()) return flattened
    const needle = query.trim().toUpperCase()
    return flattened.filter((q) => q.symbol.includes(needle) || String(q.strike).includes(needle))
  }, [chain, query])

  return (
    <aside className="flex w-[300px] shrink-0 flex-col border-r border-border-primary bg-bg-primary">
      {/* Search */}
      <div className="border-b border-border-primary p-2.5">
        <label className="flex items-center gap-2 rounded bg-bg-tertiary px-2.5 py-1.5 text-xs">
          <Search size={13} className="shrink-0 text-text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search eg: 25500 CE, 25000 PE"
            className="w-full bg-transparent text-text-primary outline-none placeholder:text-text-muted"
          />
          <kbd className="shrink-0 rounded border border-border-primary px-1 py-0.5 text-[10px] text-text-muted">
            &#x2318;K
          </kbd>
        </label>
      </div>

      {/* Count + Status */}
      <div className="flex items-center justify-between border-b border-border-secondary px-3 py-1.5 text-[11px]">
        <span className="text-text-muted">
          Options ({quotes.length})
        </span>
        {snapshot?.market_status && (
          <span className={`flex items-center gap-1.5 ${snapshot.market_status === 'OPEN' ? 'text-profit' : 'text-text-muted'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${snapshot.market_status === 'OPEN' ? 'bg-profit' : 'bg-text-muted'}`} />
            {snapshot.market_status}
          </span>
        )}
      </div>

      {/* Quote List */}
      <div className="flex-1 overflow-auto">
        {quotes.map((quote) => {
          const active = selectedQuote?.symbol === quote.symbol
          return (
            <button
              key={quote.symbol}
              onClick={() => setSelectedQuote(quote)}
              className={`group flex w-full items-center justify-between border-b border-border-secondary/40 px-3 py-2 text-left transition-colors ${
                active ? 'bg-bg-secondary' : 'hover:bg-bg-secondary/50'
              }`}
            >
              <div>
                <div className={`text-xs font-medium ${quote.option_type === 'CE' ? 'text-profit' : 'text-loss'}`}>
                  {quote.symbol}
                </div>
                <div className="text-[10px] text-text-muted">{quote.expiry}</div>
              </div>
              <div className="text-right">
                <div className="text-xs tabular-nums text-text-primary">{quote.ltp.toFixed(2)}</div>
                <div className="text-[10px] tabular-nums text-text-muted">
                  {quote.bid?.toFixed(2) ?? '--'} &times; {quote.ask?.toFixed(2) ?? '--'}
                </div>
              </div>
            </button>
          )
        })}
        {quotes.length === 0 && (
          <div className="px-3 py-10 text-center text-xs text-text-muted">
            {chain ? 'No matches' : 'Loading option chain\u2026'}
          </div>
        )}
      </div>
    </aside>
  )
}
