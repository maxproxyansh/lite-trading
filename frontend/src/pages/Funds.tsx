import { useStore } from '../store/useStore'

const metrics = [
  ['Cash Balance', 'cash_balance'],
  ['Blocked Margin', 'blocked_margin'],
  ['Blocked Premium', 'blocked_premium'],
  ['Available Funds', 'available_funds'],
  ['Realised P&L', 'realized_pnl'],
  ['Unrealised P&L', 'unrealized_pnl'],
  ['Total Equity', 'total_equity'],
] as const

export default function Funds() {
  const { funds, selectedPortfolioId } = useStore()

  return (
    <div className="p-4">
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-text-primary">Funds & Margin</h1>
        <p className="text-sm text-text-muted">Portfolio ledger, blocked funds and available buying power for {selectedPortfolioId}.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {metrics.map(([label, key]) => (
          <div key={key} className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
            <div className="text-xs uppercase tracking-[0.16em] text-text-muted">{label}</div>
            <div className={`mt-3 text-2xl font-semibold tabular-nums ${
              key.includes('pnl') && (funds?.[key] ?? 0) < 0 ? 'text-loss' : key.includes('pnl') ? 'text-profit' : 'text-text-primary'
            }`}>
              {funds ? funds[key].toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '--'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
