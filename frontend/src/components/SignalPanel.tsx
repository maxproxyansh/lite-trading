import { useShallow } from 'zustand/react/shallow'

import { useStore } from '../store/useStore'

export default function SignalPanel() {
  const { latestSignal, setSelectedQuote, chain } = useStore(useShallow((state) => ({
    latestSignal: state.latestSignal,
    setSelectedQuote: state.setSelectedQuote,
    chain: state.chain,
  })))

  if (!latestSignal) return null

  const dirBg =
    latestSignal.direction === 'BULLISH' ? 'bg-profit/15 text-profit' :
    latestSignal.direction === 'BEARISH' ? 'bg-loss/15 text-loss' :
    'bg-neutral/15 text-neutral'

  const confidencePct = Math.min(100, Math.max(0, latestSignal.confidence_score))
  const confidenceBarColor =
    latestSignal.confidence_score >= 70 ? 'bg-profit' :
    latestSignal.confidence_score >= 55 ? 'bg-signal' :
    'bg-loss'

  return (
    <div className="border-b border-border-primary px-3 py-2">
      {/* Header row: direction badge + confidence */}
      <div className="flex items-center gap-2">
        <span className={`inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-semibold ${dirBg}`}>
          {latestSignal.direction}
        </span>
        <div className="flex-1 flex items-center gap-1.5">
          <div className="flex-1 h-1 rounded-sm bg-bg-primary">
            <div
              className={`h-full rounded-sm ${confidenceBarColor}`}
              style={{ width: `${confidencePct}%` }}
            />
          </div>
          <span className="text-[10px] tabular-nums text-text-muted">{confidencePct.toFixed(0)}%</span>
        </div>
      </div>

      {/* Trade details: compact 2-col grid */}
      <div className="mt-1.5 flex items-baseline gap-3 text-[11px] text-text-muted">
        <span className="text-text-secondary">{latestSignal.strike ?? '--'} {latestSignal.option_type ?? ''}</span>
        <span>{latestSignal.expiry ?? '--'}</span>
      </div>
      <div className="mt-1 flex items-baseline gap-3 text-[11px] tabular-nums text-text-muted">
        <span>
          E {latestSignal.entry_low && latestSignal.entry_high
            ? `${latestSignal.entry_low.toFixed(1)}-${latestSignal.entry_high.toFixed(1)}`
            : '--'}
        </span>
        <span>T {latestSignal.target_price?.toFixed(1) ?? '--'}</span>
        <span>SL {latestSignal.stop_loss?.toFixed(1) ?? '--'}</span>
      </div>

      {/* Load button */}
      <button
        disabled={!latestSignal.option_type || !latestSignal.strike || !latestSignal.expiry || !chain}
        onClick={() => {
          const quote = chain?.rows.flatMap((row) => [row.call, row.put]).find((q) =>
            q.expiry === latestSignal.expiry &&
            q.strike === latestSignal.strike &&
            q.option_type === latestSignal.option_type,
          )
          if (quote) setSelectedQuote(quote)
        }}
        className="mt-1.5 text-[11px] text-signal hover:text-signal/80 font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      >
        Load into ticket →
      </button>
    </div>
  )
}
