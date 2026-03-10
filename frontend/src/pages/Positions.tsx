import { closePosition } from '../lib/api'
import { useStore } from '../store/useStore'

export default function Positions() {
  const { positions, portfolioLoading, addToast } = useStore()

  return (
    <div>
      <div className="flex items-center justify-between border-b border-border-primary px-3 h-9">
        <h1 className="text-[12px] font-medium text-text-primary">
          Positions{positions.length > 0 && <span className="ml-1 text-text-muted">({positions.length})</span>}
        </h1>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b border-border-primary text-[11px] text-text-muted">
            <tr>
              <th className="px-3 py-[3px] text-left font-normal">Symbol</th>
              <th className="px-3 py-[3px] text-right font-normal">Net Qty</th>
              <th className="px-3 py-[3px] text-right font-normal">Avg</th>
              <th className="px-3 py-[3px] text-right font-normal">LTP</th>
              <th className="px-3 py-[3px] text-right font-normal">Unrealised</th>
              <th className="px-3 py-[3px] text-right font-normal">Margin</th>
              <th className="px-3 py-[3px] text-right font-normal"></th>
            </tr>
          </thead>
          <tbody>
            {portfolioLoading ? (
              <tr><td colSpan={7} className="py-12 text-center"><div className="flex items-center justify-center"><div className="h-5 w-5 rounded-full border-2 border-signal border-t-transparent animate-spin" /></div></td></tr>
            ) : positions.length === 0 ? (
              <tr><td colSpan={7} className="py-12 text-center text-xs text-text-muted">No open positions</td></tr>
            ) : (
              positions.map((pos) => (
                <tr key={pos.id} className="border-b border-border-secondary/40 hover:bg-bg-secondary/30">
                  <td className="px-3 py-1.5 text-text-primary">{pos.symbol}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">{pos.net_quantity}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">{pos.average_open_price.toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">{pos.last_price.toFixed(2)}</td>
                  <td className={`px-3 py-1.5 text-right tabular-nums font-medium ${pos.unrealized_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                    {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl.toFixed(2)}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-secondary">{pos.blocked_margin.toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-right">
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
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
