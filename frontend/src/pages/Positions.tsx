import { closePosition } from '../lib/api'
import { useStore } from '../store/useStore'
import { SkeletonTable } from '../components/Skeleton'
import { useShallow } from 'zustand/react/shallow'

export default function Positions() {
  const { positions, portfolioLoading, addToast, selectedPortfolioId, requestPortfolioRefresh } = useStore(useShallow((state) => ({
    positions: state.positions,
    portfolioLoading: state.portfolioLoading,
    addToast: state.addToast,
    selectedPortfolioId: state.selectedPortfolioId,
    requestPortfolioRefresh: state.requestPortfolioRefresh,
  })))

  if (portfolioLoading) return <SkeletonTable rows={8} cols={7} />

  return (
    <div>
      <div className="flex items-center justify-between border-b border-border-primary px-3 h-9">
        <h1 className="text-[12px] font-medium text-text-primary">
          Positions{positions.length > 0 && <span className="ml-1 text-text-muted">({positions.length})</span>}
        </h1>
      </div>

      {positions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-text-muted">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" className="mb-4 opacity-30">
            <rect x="8" y="8" width="32" height="32" rx="1" stroke="currentColor" strokeWidth="1.5" />
            <line x1="16" y1="18" x2="32" y2="18" stroke="currentColor" strokeWidth="1.5" />
            <line x1="16" y1="24" x2="28" y2="24" stroke="currentColor" strokeWidth="1.5" />
            <line x1="16" y1="30" x2="24" y2="30" stroke="currentColor" strokeWidth="1.5" />
          </svg>
          <p className="text-sm">No open positions</p>
          <p className="text-xs mt-1">Your active positions will appear here</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b border-border-primary">
              <tr>
                <th className="px-3 py-[3px] text-left font-normal text-xs text-text-muted uppercase tracking-wider">Symbol</th>
                <th className="px-3 py-[3px] text-right font-normal text-xs text-text-muted uppercase tracking-wider w-20">Net Qty</th>
                <th className="px-3 py-[3px] text-right font-normal text-xs text-text-muted uppercase tracking-wider">Avg</th>
                <th className="px-3 py-[3px] text-right font-normal text-xs text-text-muted uppercase tracking-wider">LTP</th>
                <th className="px-3 py-[3px] text-right font-normal text-xs text-text-muted uppercase tracking-wider">Unrealised</th>
                <th className="px-3 py-[3px] text-right font-normal text-xs text-text-muted uppercase tracking-wider">Margin</th>
                <th className="px-3 py-[3px] text-right font-normal text-xs text-text-muted uppercase tracking-wider w-16"></th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => (
                <tr key={pos.id} className="border-b border-border-secondary/40 hover:bg-bg-hover transition-colors">
                  <td className="px-3 py-1.5 text-text-primary">{pos.symbol}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">{pos.net_quantity}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">₹{pos.average_open_price.toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">₹{pos.last_price.toFixed(2)}</td>
                  <td className={`px-3 py-1.5 text-right tabular-nums font-medium ${pos.unrealized_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                    {pos.unrealized_pnl >= 0 ? '+' : ''}₹{Math.abs(pos.unrealized_pnl).toFixed(2)}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-secondary">₹{pos.blocked_margin.toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-right">
                    <button
                      onClick={async () => {
                        try {
                          await closePosition(pos.id)
                          addToast('success', `Close submitted for ${pos.symbol}`)
                          requestPortfolioRefresh(selectedPortfolioId)
                        } catch (error) {
                          addToast('error', error instanceof Error ? error.message : 'Close failed')
                        }
                      }}
                      className="rounded border border-loss/30 px-2 py-1 text-[11px] text-loss transition-colors hover:bg-loss/10"
                    >
                      Exit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
