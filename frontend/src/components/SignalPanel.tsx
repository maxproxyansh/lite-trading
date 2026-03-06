import { Bot, Target, TriangleAlert } from 'lucide-react'

import { useStore } from '../store/useStore'

export default function SignalPanel() {
  const { latestSignal, setSelectedQuote, chain } = useStore()

  if (!latestSignal) {
    return (
      <div className="border-b border-border-primary p-3">
        <div className="text-xs text-text-muted">No signal loaded</div>
      </div>
    )
  }

  const tone =
    latestSignal.confidence_score >= 70 ? 'text-profit' :
    latestSignal.confidence_score >= 55 ? 'text-signal' :
    'text-loss'

  return (
    <div className="border-b border-border-primary p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-medium text-text-primary">
          <Bot size={13} className="text-signal" />
          Agent Signal
        </div>
        <span className={`text-[11px] font-medium ${tone}`}>
          {latestSignal.confidence_label} {latestSignal.confidence_score.toFixed(0)}%
        </span>
      </div>

      <div className="space-y-1.5 text-[11px] text-text-secondary">
        <div>
          <span className="text-text-muted">Direction </span>
          <span className="font-medium text-text-primary">{latestSignal.direction}</span>
        </div>
        <div>
          <span className="text-text-muted">Trade </span>
          <span className="text-text-primary">{latestSignal.trade_text ?? 'No actionable trade'}</span>
        </div>
        <div className="flex gap-3 text-text-muted">
          <span>{latestSignal.expiry ?? '--'}</span>
          <span>{latestSignal.strike ?? '--'} {latestSignal.option_type ?? ''}</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded bg-bg-primary px-2 py-1.5">
            <div className="text-[10px] text-text-muted">Entry</div>
            <div className="tabular-nums text-text-primary">
              {latestSignal.entry_low && latestSignal.entry_high
                ? `${latestSignal.entry_low.toFixed(1)} - ${latestSignal.entry_high.toFixed(1)}`
                : '--'}
            </div>
          </div>
          <div className="rounded bg-bg-primary px-2 py-1.5">
            <div className="text-[10px] text-text-muted">Target / Stop</div>
            <div className="tabular-nums text-text-primary">
              {latestSignal.target_price?.toFixed(1) ?? '--'} / {latestSignal.stop_loss?.toFixed(1) ?? '--'}
            </div>
          </div>
        </div>
      </div>

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
          className="flex-1 rounded bg-signal px-2 py-1.5 text-[11px] font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          Load Into Ticket
        </button>
        <div className="flex items-center justify-center rounded border border-border-primary px-2 text-text-muted">
          {latestSignal.target_valid && latestSignal.stop_valid ? <Target size={12} /> : <TriangleAlert size={12} />}
        </div>
      </div>
    </div>
  )
}
