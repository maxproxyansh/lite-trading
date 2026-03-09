import { Target, TriangleAlert } from 'lucide-react'

import { useStore } from '../store/useStore'

export default function SignalPanel() {
  const { latestSignal, setSelectedQuote, chain } = useStore()

  if (!latestSignal) {
    return (
      <div className="border-b border-border-primary p-2">
        <div className="text-xs text-text-muted">No signal loaded</div>
      </div>
    )
  }

  const tone =
    latestSignal.confidence_score >= 70 ? 'text-profit' :
    latestSignal.confidence_score >= 55 ? 'text-signal' :
    'text-loss'

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
    <div className="border-b border-border-primary p-2">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] text-text-muted uppercase tracking-wide">Agent Signal</span>
        <span className="bg-profit/20 text-profit text-[10px] px-1.5 py-0.5 rounded">
          {latestSignal.confidence_label} {latestSignal.confidence_score.toFixed(0)}%
        </span>
      </div>

      <div className="border-t border-border-primary/60" />

      {/* Direction badge - prominent */}
      <div className={`my-2 flex items-center justify-center rounded-sm px-3 py-3 ${dirBg}`}>
        <span className="text-[22px] font-semibold tracking-tight">{latestSignal.direction}</span>
      </div>

      {/* Confidence bar */}
      <div className="mb-2">
        <div className="mb-0.5 flex items-center justify-between">
          <span className="text-[10px] text-text-muted">Confidence</span>
          <span className={`text-[10px] font-medium ${tone}`}>{confidencePct.toFixed(0)}%</span>
        </div>
        <div className="h-[3px] w-full rounded-sm bg-bg-primary">
          <div
            className={`h-full rounded-sm ${confidenceBarColor}`}
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>

      <div className="border-t border-border-primary/60" />

      <div className="mt-2 space-y-1.5 text-[11px] text-text-secondary">
        <div>
          <span className="text-text-muted">Trade </span>
          <span className="text-text-primary">{latestSignal.trade_text ?? 'No actionable trade'}</span>
        </div>
        <div className="flex gap-3 text-text-muted">
          <span>{latestSignal.expiry ?? '--'}</span>
          <span>{latestSignal.strike ?? '--'} {latestSignal.option_type ?? ''}</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-sm bg-bg-primary px-2 py-1">
            <div className="text-[10px] text-text-muted">Entry</div>
            <div className="tabular-nums text-text-primary">
              {latestSignal.entry_low && latestSignal.entry_high
                ? `${latestSignal.entry_low.toFixed(1)} - ${latestSignal.entry_high.toFixed(1)}`
                : '--'}
            </div>
          </div>
          <div className="rounded-sm bg-bg-primary px-2 py-1">
            <div className="text-[10px] text-text-muted">Target / Stop</div>
            <div className="tabular-nums text-text-primary">
              {latestSignal.target_price?.toFixed(1) ?? '--'} / {latestSignal.stop_loss?.toFixed(1) ?? '--'}
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-border-primary/60 mt-2" />

      <div className="mt-2 flex gap-2">
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
          className="flex-1 h-[36px] rounded-[4px] bg-signal px-2 text-[11px] font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          Load Into Ticket
        </button>
        <div className="self-stretch flex items-center justify-center rounded-sm border border-border-primary px-2 text-text-muted">
          {latestSignal.target_valid && latestSignal.stop_valid ? <Target size={12} /> : <TriangleAlert size={12} />}
        </div>
      </div>
    </div>
  )
}
