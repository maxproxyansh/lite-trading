import { useShallow } from 'zustand/react/shallow'

import { useStore } from '../store/useStore'

interface Props {
  maxVisible?: number
}

function formatExpiry(dateStr: string): string {
  const date = new Date(`${dateStr}T00:00:00`)
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export default function ExpiryTabs({ maxVisible = 5 }: Props) {
  const { expiries, selectedExpiry, activeExpiry, setSelectedExpiry } = useStore(useShallow((state) => ({
    expiries: state.snapshot?.expiries ?? [],
    selectedExpiry: state.selectedExpiry,
    activeExpiry: state.snapshot?.active_expiry ?? null,
    setSelectedExpiry: state.setSelectedExpiry,
  })))
  const visibleExpiries = expiries.slice(0, maxVisible)
  const active = selectedExpiry ?? activeExpiry ?? ''

  return (
    <div className="flex items-center justify-center gap-1 overflow-x-auto px-3 py-1.5">
      {visibleExpiries.map((expiry) => (
        <button
          key={expiry}
          onClick={() => setSelectedExpiry(expiry)}
          className={`shrink-0 rounded-sm px-2.5 py-0.5 text-[11px] font-medium transition-colors ${
            expiry === active
              ? 'bg-brand text-bg-primary'
              : 'text-text-muted hover:bg-bg-hover hover:text-text-primary'
          }`}
        >
          {formatExpiry(expiry)}
        </button>
      ))}
    </div>
  )
}
