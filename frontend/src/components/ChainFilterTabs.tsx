import { useStore } from '../store/useStore'

const FILTERS = ['ALL', 'ITM', 'ATM', 'OTM'] as const

export default function ChainFilterTabs() {
  const { chainFilter, setChainFilter } = useStore()

  return (
    <div className="flex items-center justify-center gap-1 px-3 py-1.5">
      {FILTERS.map((f) => (
        <button
          key={f}
          onClick={() => setChainFilter(f)}
          className={`px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide transition-colors rounded-sm ${
            f === chainFilter
              ? 'bg-bg-hover text-text-primary'
              : 'text-text-muted hover:text-text-secondary'
          }`}
        >
          {f === 'ALL' ? 'Full' : f}
        </button>
      ))}
    </div>
  )
}
