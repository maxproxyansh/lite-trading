import { useStore } from '../store/useStore'

function formatExpiry(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

interface Props {
  maxVisible?: number
}

export default function ExpiryTabs({ maxVisible = 4 }: Props) {
  const { snapshot, selectedExpiry, setSelectedExpiry } = useStore()
  const expiries = snapshot?.expiries?.slice(0, maxVisible) ?? []
  const active = selectedExpiry ?? snapshot?.active_expiry ?? ''

  return (
    <div className="flex items-center justify-center gap-1 overflow-x-auto px-3 py-1.5">
      {expiries.map((exp) => (
        <button
          key={exp}
          onClick={() => setSelectedExpiry(exp)}
          className={`shrink-0 px-2.5 py-0.5 text-[11px] font-medium transition-colors rounded-sm ${
            exp === active
              ? 'bg-brand text-bg-primary'
              : 'text-text-muted hover:text-text-primary hover:bg-bg-hover'
          }`}
        >
          {formatExpiry(exp)}
        </button>
      ))}
    </div>
  )
}
