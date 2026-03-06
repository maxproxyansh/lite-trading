import { Bot, Target, TriangleAlert } from 'lucide-react'

import { useStore } from '../store/useStore'

export default function SignalPanel() {
  const { latestSignal, setSelectedQuote, chain } = useStore()

  if (!latestSignal) {
    return (
      <div className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
        <div className="text-xs text-text-muted">No signal loaded.</div>
      </div>
    )
  }

  const confidenceTone = latestSignal.confidence_score >= 70 ? 'text-profit' : latestSignal.confidence_score >= 55 ? 'text-signal' : 'text-loss'

  return (
    <div className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Bot size={16} className="text-signal" />
          Agent Signal
        </div>
        <div className={`text-xs font-medium ${confidenceTone}`}>
          {latestSignal.confidence_label} {latestSignal.confidence_score.toFixed(1)}%
        </div>
      </div>

      <div className="space-y-2 text-xs text-text-secondary">
        <div>
          <span className="text-text-muted">Direction </span>
          <span className="font-medium text-text-primary">{latestSignal.direction}</span>
        </div>
        <div>
          <span className="text-text-muted">Trade </span>
          <span className="font-medium text-text-primary">{latestSignal.trade_text ?? 'No actionable trade'}</span>
        </div>
        <div className="flex items-center gap-4">
          <span>Expiry: <span className="text-text-primary">{latestSignal.expiry ?? '--'}</span></span>
          <span>Strike: <span className="text-text-primary">{latestSignal.strike ?? '--'}</span></span>
          <span>Type: <span className="text-text-primary">{latestSignal.option_type ?? '--'}</span></span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-xl bg-bg-primary p-2">
            <div className="text-[11px] text-text-muted">Entry</div>
            <div className="tabular-nums text-text-primary">
              {latestSignal.entry_low && latestSignal.entry_high
                ? `${latestSignal.entry_low.toFixed(1)} - ${latestSignal.entry_high.toFixed(1)}`
                : '--'}
            </div>
          </div>
          <div className="rounded-xl bg-bg-primary p-2">
            <div className="text-[11px] text-text-muted">Target / Stop</div>
            <div className="tabular-nums text-text-primary">
              {latestSignal.target_price ? latestSignal.target_price.toFixed(1) : '--'} / {latestSignal.stop_loss ? latestSignal.stop_loss.toFixed(1) : '--'}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          disabled={!latestSignal.option_type || !latestSignal.strike || !latestSignal.expiry || !chain}
          onClick={() => {
            const quote = chain?.rows.flatMap((row) => [row.call, row.put]).find((item) =>
              item.expiry === latestSignal.expiry &&
              item.strike === latestSignal.strike &&
              item.option_type === latestSignal.option_type,
            )
            if (quote) {
              setSelectedQuote(quote)
            }
          }}
          className="flex-1 rounded-xl bg-signal px-3 py-2 text-xs font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Load Into Ticket
        </button>
        <div className="flex items-center justify-center rounded-xl border border-border-primary px-3 text-text-muted">
          {latestSignal.target_valid && latestSignal.stop_valid ? <Target size={14} /> : <TriangleAlert size={14} />}
        </div>
      </div>
    </div>
  )
}
