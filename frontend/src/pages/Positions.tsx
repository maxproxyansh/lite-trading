import LoadingState from '../components/LoadingState'
import { closePosition } from '../lib/api'
import { useStore } from '../store/useStore'

export default function Positions() {
  const { positions, portfolioLoading, addToast } = useStore()

  return (
    <div className="p-4">
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-text-primary">Open Positions</h1>
        <p className="text-sm text-text-muted">Net option exposures with live mark-to-market.</p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-border-primary bg-bg-secondary">
        <table className="w-full text-sm">
          <thead className="bg-bg-primary text-text-muted">
            <tr>
              <th className="px-4 py-3 text-left">Symbol</th>
              <th className="px-4 py-3 text-right">Net Qty</th>
              <th className="px-4 py-3 text-right">Avg</th>
              <th className="px-4 py-3 text-right">LTP</th>
              <th className="px-4 py-3 text-right">Unrealised</th>
              <th className="px-4 py-3 text-right">Margin</th>
              <th className="px-4 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={7} className="p-0">
                <LoadingState loading={portfolioLoading} empty={positions.length === 0} emptyText="No open positions.">
                  <table className="w-full text-sm">
                    <tbody>
                      {positions.map((position) => (
                        <tr key={position.id} className="border-t border-border-primary/50">
                          <td className="px-4 py-3 text-text-primary">{position.symbol}</td>
                          <td className="px-4 py-3 text-right tabular-nums text-text-primary">{position.net_quantity}</td>
                          <td className="px-4 py-3 text-right tabular-nums text-text-primary">{position.average_open_price.toFixed(2)}</td>
                          <td className="px-4 py-3 text-right tabular-nums text-text-primary">{position.last_price.toFixed(2)}</td>
                          <td className={`px-4 py-3 text-right tabular-nums ${position.unrealized_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                            {position.unrealized_pnl >= 0 ? '+' : ''}{position.unrealized_pnl.toFixed(2)}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums text-text-primary">{position.blocked_margin.toFixed(2)}</td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={async () => {
                                try {
                                  await closePosition(position.id)
                                  addToast('success', `Close order submitted for ${position.symbol}`)
                                } catch (error) {
                                  addToast('error', error instanceof Error ? error.message : 'Close failed')
                                }
                              }}
                              className="rounded-xl border border-loss/30 px-3 py-1.5 text-xs text-loss transition hover:bg-loss/10"
                            >
                              Close
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </LoadingState>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
