import LoadingState from '../components/LoadingState'
import { useStore } from '../store/useStore'

function formatCurrency(value: number): string {
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export default function Funds() {
  const { funds, portfolioLoading } = useStore()

  const breakdownItems = [
    { label: 'Cash Balance', value: funds?.cash_balance ?? 0, isPnl: false },
    { label: 'Blocked Margin', value: funds?.blocked_margin ?? 0, isPnl: false },
    { label: 'Blocked Premium', value: funds?.blocked_premium ?? 0, isPnl: false },
    { label: 'Available Funds', value: funds?.available_funds ?? 0, isPnl: false },
    { label: 'Realised P&L', value: funds?.realized_pnl ?? 0, isPnl: true },
    { label: 'Unrealised P&L', value: funds?.unrealized_pnl ?? 0, isPnl: true },
    { label: 'Total Equity', value: funds?.total_equity ?? 0, isPnl: false },
  ]

  return (
    <div>
      <div className="flex items-center justify-between border-b border-border-primary px-3 h-9">
        <h1 className="text-[12px] font-medium text-text-primary">Funds</h1>
      </div>

      <div className="p-3">
        <LoadingState loading={portfolioLoading} empty={!funds} emptyText="Funds data unavailable">
          <div className="mb-4 grid grid-cols-2 gap-4">
            {/* Equity */}
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-[12px] text-text-secondary">
                <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                Equity
              </div>
              <div className="flex items-start gap-8">
                <div>
                  <div className="text-[16px] font-semibold tabular-nums text-text-primary">
                    {formatCurrency(funds?.available_funds ?? 0)}
                  </div>
                  <div className="mt-1 text-xs text-text-muted">Margin available</div>
                </div>
                <div className="space-y-1.5 text-xs">
                  <div className="text-text-secondary">
                    Margins used{' '}
                    <span className="tabular-nums font-medium text-text-primary">{formatCurrency(funds?.blocked_margin ?? 0)}</span>
                  </div>
                  <div className="text-text-secondary">
                    Opening balance{' '}
                    <span className="tabular-nums font-medium text-text-primary">{formatCurrency(funds?.cash_balance ?? 0)}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* P&L Summary */}
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-[12px] text-text-secondary">
                <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>
                </svg>
                P&amp;L
              </div>
              <div className="flex items-start gap-8">
                <div>
                  <div className={`text-[16px] font-semibold tabular-nums ${(funds?.realized_pnl ?? 0) >= 0 ? 'text-profit' : 'text-loss'}`}>
                    {(funds?.realized_pnl ?? 0) >= 0 ? '+' : ''}{formatCurrency(funds?.realized_pnl ?? 0)}
                  </div>
                  <div className="mt-1 text-xs text-text-muted">Realised</div>
                </div>
                <div className="space-y-1.5 text-xs">
                  <div className="text-text-secondary">
                    Unrealised{' '}
                    <span className={`tabular-nums font-medium ${(funds?.unrealized_pnl ?? 0) >= 0 ? 'text-profit' : 'text-loss'}`}>
                      {(funds?.unrealized_pnl ?? 0) >= 0 ? '+' : ''}{formatCurrency(funds?.unrealized_pnl ?? 0)}
                    </span>
                  </div>
                  <div className="text-text-secondary">
                    Total equity{' '}
                    <span className="tabular-nums font-medium text-text-primary">{formatCurrency(funds?.total_equity ?? 0)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Breakdown */}
          <div className="mt-6">
            <h3 className="text-sm font-medium text-text-primary mb-3 px-4">Fund Breakdown</h3>
            <table className="w-full text-sm">
              <tbody>
                {breakdownItems.map(item => (
                  <tr key={item.label} className="border-b border-border-secondary">
                    <td className="px-4 py-2 text-text-muted">{item.label}</td>
                    <td className={`px-4 py-2 text-right font-medium tabular-nums ${
                      item.isPnl && item.value < 0 ? 'text-loss' :
                      item.isPnl && item.value > 0 ? 'text-profit' :
                      'text-text-primary'
                    }`}>
                      {formatCurrency(item.value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </LoadingState>
      </div>
    </div>
  )
}
