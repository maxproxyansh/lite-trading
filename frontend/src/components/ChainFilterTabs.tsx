import { useShallow } from 'zustand/react/shallow'

import { useStore } from '../store/useStore'

const FILTERS = ['ALL', 'ITM', 'ATM', 'OTM'] as const

export default function ChainFilterTabs() {
  const { chainFilter, setChainFilter } = useStore(useShallow((state) => ({
    chainFilter: state.chainFilter,
    setChainFilter: state.setChainFilter,
  })))

  return (
    <div className="flex items-center justify-center gap-1 px-3 py-1.5">
      {FILTERS.map((filter) => (
        <button
          key={filter}
          onClick={() => setChainFilter(filter)}
          className={`rounded-sm px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide transition-colors ${
            filter === chainFilter
              ? 'bg-bg-hover text-text-primary'
              : 'text-text-muted hover:text-text-secondary'
          }`}
        >
          {filter === 'ALL' ? 'Full' : filter}
        </button>
      ))}
    </div>
  )
}
