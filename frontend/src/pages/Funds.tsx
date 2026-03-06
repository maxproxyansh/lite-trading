import LoadingState from '../components/LoadingState'
import { useStore } from '../store/useStore'

function fmt(value: number): string {
  if (Math.abs(value) >= 100000) return `${(value / 100000).toFixed(2)}L`
  return value.toLocaleString('en-IN', { maximumFractionDigits: 2 })
}

export default function Funds() {
  const { funds, user, portfolioLoading } = useStore()

  return (
    <div className="p-5">
      <h1 className="mb-6 text-lg text-text-primary">Hi, {user?.display_name ?? 'Trader'}</h1>

      <LoadingState loading={portfolioLoading} empty={!funds} emptyText="Funds data unavailable">
        <div className="mb-8 grid grid-cols-2 gap-8">
          {/* Equity */}
          <div>
            <div className="mb-3 flex items-center gap-2 text-sm text-text-secondary">
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
              Equity
            </div>
            <div className="flex items-start gap-8">
              <div>
                <div className="text-3xl font-medium tabular-nums text-text-primary">
                  {fmt(funds?.available_funds ?? 0)}
                </div>
                <div className="mt-1 text-xs text-text-muted">Margin available</div>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="text-text-secondary">
                  Margins used{' '}
                  <span className="tabular-nums font-medium text-text-primary">{fmt(funds?.blocked_margin ?? 0)}</span>
                </div>
                <div className="text-text-secondary">
                  Opening balance{' '}
                  <span className="tabular-nums font-medium text-text-primary">{fmt(funds?.cash_balance ?? 0)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* P&L Summary */}
          <div>
            <div className="mb-3 flex items-center gap-2 text-sm text-text-secondary">
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>
              </svg>
              P&amp;L
            </div>
            <div className="flex items-start gap-8">
              <div>
                <div className={`text-3xl font-medium tabular-nums ${(funds?.realized_pnl ?? 0) >= 0 ? 'text-profit' : 'text-loss'}`}>
                  {(funds?.realized_pnl ?? 0) >= 0 ? '+' : ''}{fmt(funds?.realized_pnl ?? 0)}
                </div>
                <div className="mt-1 text-xs text-text-muted">Realised</div>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="text-text-secondary">
                  Unrealised{' '}
                  <span className={`tabular-nums font-medium ${(funds?.unrealized_pnl ?? 0) >= 0 ? 'text-profit' : 'text-loss'}`}>
                    {(funds?.unrealized_pnl ?? 0) >= 0 ? '+' : ''}{fmt(funds?.unrealized_pnl ?? 0)}
                  </span>
                </div>
                <div className="text-text-secondary">
                  Total equity{' '}
                  <span className="tabular-nums font-medium text-text-primary">{fmt(funds?.total_equity ?? 0)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Breakdown */}
        <div className="border-t border-border-primary pt-5">
          <h2 className="mb-3 text-sm font-medium text-text-secondary">Fund Breakdown</h2>
          <div className="grid grid-cols-3 gap-3 text-xs xl:grid-cols-4">
            {([
              ['Cash Balance', funds?.cash_balance],
              ['Blocked Margin', funds?.blocked_margin],
              ['Blocked Premium', funds?.blocked_premium],
              ['Available Funds', funds?.available_funds],
              ['Realised P&L', funds?.realized_pnl],
              ['Unrealised P&L', funds?.unrealized_pnl],
              ['Total Equity', funds?.total_equity],
            ] as const).map(([label, value]) => (
              <div key={label} className="rounded bg-bg-secondary p-3">
                <div className="mb-1 text-[10px] uppercase tracking-wider text-text-muted">{label}</div>
                <div className={`text-sm font-medium tabular-nums ${
                  label.includes('P&L') && (value ?? 0) < 0 ? 'text-loss' :
                  label.includes('P&L') && (value ?? 0) > 0 ? 'text-profit' :
                  'text-text-primary'
                }`}>
                  {value != null ? value.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '--'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </LoadingState>
    </div>
  )
}
