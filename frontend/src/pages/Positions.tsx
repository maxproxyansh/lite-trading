import LoadingState from '../components/LoadingState'
import { closePosition } from '../lib/api'
import { useStore } from '../store/useStore'

export default function Positions() {
  const { positions, portfolioLoading, addToast } = useStore()

  return (
    <div className="p-5">
      <h1 className="mb-4 text-base font-medium text-text-primary">Positions</h1>

      <table className="w-full text-xs">
        <thead className="border-b border-border-primary text-[11px] text-text-muted">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Symbol</th>
            <th className="px-3 py-2 text-right font-medium">Net Qty</th>
            <th className="px-3 py-2 text-right font-medium">Avg</th>
            <th className="px-3 py-2 text-right font-medium">LTP</th>
            <th className="px-3 py-2 text-right font-medium">Unrealised</th>
            <th className="px-3 py-2 text-right font-medium">Margin</th>
            <th className="px-3 py-2 text-right font-medium"></th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={7} className="p-0">
              <LoadingState loading={portfolioLoading} empty={positions.length === 0} emptyText="No open positions">
                <table className="w-full text-xs">
                  <tbody>
                    {positions.map((pos) => (
                      <tr key={pos.id} className="border-b border-border-secondary/40 hover:bg-bg-secondary/30">
                        <td className="px-3 py-2.5 text-text-primary">{pos.symbol}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-text-primary">{pos.net_quantity}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-text-primary">{pos.average_open_price.toFixed(2)}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-text-primary">{pos.last_price.toFixed(2)}</td>
                        <td className={`px-3 py-2.5 text-right tabular-nums font-medium ${pos.unrealized_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                          {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl.toFixed(2)}
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-text-secondary">{pos.blocked_margin.toFixed(2)}</td>
                        <td className="px-3 py-2.5 text-right">
                          <button
                            onClick={async () => {
                              try {
                                await closePosition(pos.id)
                                addToast('success', `Close submitted for ${pos.symbol}`)
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
              </LoadingState>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
