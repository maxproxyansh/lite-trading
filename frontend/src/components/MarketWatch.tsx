import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'

import { useStore } from '../store/useStore'

export default function MarketWatch() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [showSearch, setShowSearch] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)
  const { chain, selectedQuote, setSelectedQuote, snapshot } = useStore(useShallow((state) => ({
    chain: state.chain,
    selectedQuote: state.selectedQuote,
    setSelectedQuote: state.setSelectedQuote,
    snapshot: state.snapshot,
  })))

  const quotes = useMemo(() => {
    if (!chain) return []
    const flattened = chain.rows.flatMap((row) => [row.call, row.put])
    if (!query.trim()) return flattened
    const needle = query.trim().toUpperCase()
    return flattened.filter((q) => q.symbol.includes(needle) || String(q.strike).includes(needle))
  }, [chain, query])

  // Cmd+K shortcut
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setShowSearch(true)
        setTimeout(() => searchRef.current?.focus(), 0)
      }
      if (e.key === 'Escape') {
        setShowSearch(false)
        setQuery('')
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  return (
    <aside className="flex w-[300px] shrink-0 flex-col border-r border-border-primary bg-bg-primary">
      {/* Search bar */}
      <div className="border-b border-border-primary px-2.5 py-2">
        <div
          className="flex cursor-text items-center gap-2 bg-bg-tertiary px-2.5 py-[6px] text-[12px]"
          onClick={() => {
            setShowSearch(true)
            setTimeout(() => searchRef.current?.focus(), 0)
          }}
        >
          <Search size={13} className="shrink-0 text-text-muted" />
          {showSearch ? (
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search eg: 25500 CE"
              className="w-full bg-transparent text-text-primary outline-none placeholder:text-text-muted"
              onBlur={() => {
                if (!query) setShowSearch(false)
              }}
            />
          ) : (
            <span className="flex-1 text-text-muted">Search eg: 25500 CE</span>
          )}
          <kbd className="shrink-0 border border-border-primary bg-bg-primary px-1 py-0.5 text-[10px] text-text-muted">
            &#x2318;K
          </kbd>
        </div>
      </div>

      {/* Count + Market status */}
      <div className="flex items-center justify-between border-b border-border-secondary px-3 py-[5px] text-[11px]">
        <span className="font-medium text-text-muted">
          Options ({quotes.length})
        </span>
        {snapshot?.market_status && (
          <span className={`flex items-center gap-1.5 ${snapshot.market_status === 'OPEN' ? 'text-profit' : 'text-text-muted'}`}>
            <span className={`h-[5px] w-[5px] rounded-full ${snapshot.market_status === 'OPEN' ? 'bg-profit' : 'bg-text-muted'}`} />
            {snapshot.market_status}
          </span>
        )}
      </div>

      {/* Quote list */}
      <div className="flex-1 overflow-auto">
        {quotes.map((quote) => {
          const active = selectedQuote?.symbol === quote.symbol
          const isCE = quote.option_type === 'CE'
          return (
            <div
              key={quote.symbol}
              onClick={() => setSelectedQuote(quote)}
              className={`group relative flex w-full cursor-pointer items-center justify-between border-b border-border-secondary/40 px-3 py-[7px] text-left transition-colors duration-100 ${
                active ? 'bg-bg-hover' : 'hover:bg-bg-hover/50'
              }`}
            >
              {/* Left: symbol + expiry */}
              <div className="min-w-0">
                <div className={`text-[12px] font-medium ${isCE ? 'text-profit' : 'text-loss'}`}>
                  {quote.symbol}
                </div>
                <div className="text-[10px] text-text-muted">{quote.expiry}</div>
              </div>

              {/* Right: B/S buttons (hover) + LTP + bid x ask */}
              <div className="flex items-center gap-2">
                {/* B/S buttons on hover */}
                <div className="flex gap-1 opacity-0 transition-opacity duration-100 group-hover:opacity-100">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedQuote(quote)
                      navigate('/')
                    }}
                    className="flex h-[18px] w-[18px] items-center justify-center bg-profit text-[9px] font-bold text-white transition-colors hover:bg-btn-buy-hover"
                    title="Buy"
                  >
                    B
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedQuote(quote)
                      navigate('/')
                    }}
                    className="flex h-[18px] w-[18px] items-center justify-center bg-loss text-[9px] font-bold text-white transition-colors hover:bg-btn-sell-hover"
                    title="Sell"
                  >
                    S
                  </button>
                </div>

                {/* Price info */}
                <div className="text-right">
                  <div className="text-[12px] tabular-nums text-text-primary">{quote.ltp.toFixed(2)}</div>
                  <div className="text-[10px] tabular-nums text-text-muted">
                    {quote.bid?.toFixed(2) ?? '--'} &times; {quote.ask?.toFixed(2) ?? '--'}
                  </div>
                </div>
              </div>
            </div>
          )
        })}
        {quotes.length === 0 && (
          <div className="px-3 py-10 text-center text-[12px] text-text-muted">
            {chain ? 'No matches' : 'Loading option chain\u2026'}
          </div>
        )}
      </div>
    </aside>
  )
}
