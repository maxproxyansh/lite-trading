import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'

import { useStore } from '../store/useStore'

export default function MarketWatch() {
  const [query, setQuery] = useState('')
  const { chain, selectedQuote, setSelectedQuote } = useStore()

  const quotes = useMemo(() => {
    if (!chain) return []
    const flattened = chain.rows.flatMap((row) => [row.call, row.put])
    if (!query.trim()) return flattened
    const needle = query.trim().toUpperCase()
    return flattened.filter((quote) => quote.symbol.includes(needle))
  }, [chain, query])

  return (
    <section className="flex h-full flex-col rounded-2xl border border-border-primary bg-bg-secondary">
      <div className="border-b border-border-primary p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">Marketwatch</div>
        <label className="flex items-center gap-2 rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-sm">
          <Search size={14} className="text-text-muted" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by strike or symbol"
            className="w-full bg-transparent text-text-primary outline-none placeholder:text-text-muted"
          />
        </label>
      </div>

      <div className="flex-1 overflow-auto">
        {quotes.map((quote) => {
          const active = selectedQuote?.symbol === quote.symbol
          return (
            <button
              key={quote.symbol}
              onClick={() => setSelectedQuote(quote)}
              className={`grid w-full grid-cols-[1fr_auto] items-center border-b border-border-primary/50 px-3 py-2 text-left transition ${
                active ? 'bg-bg-tertiary' : 'hover:bg-bg-primary/70'
              }`}
            >
              <div>
                <div className="text-xs font-medium text-text-primary">{quote.strike} {quote.option_type}</div>
                <div className="text-[11px] text-text-muted">{quote.expiry}</div>
              </div>
              <div className="text-right">
                <div className="tabular-nums text-sm text-text-primary">{quote.ltp.toFixed(2)}</div>
                <div className="text-[11px] text-text-muted">
                  B {quote.bid?.toFixed(2) ?? '--'} / A {quote.ask?.toFixed(2) ?? '--'}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}
