import { useStore } from '../store/useStore'

export default function History() {
  const { orders, portfolioLoading } = useStore()
  const fills = orders.filter((order) => order.status === 'FILLED')

  return (
    <div>
      <div className="flex items-center justify-between border-b border-border-primary px-3 h-9">
        <h1 className="text-[12px] font-medium text-text-primary">Tradebook</h1>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b border-border-primary text-[11px] text-text-muted">
            <tr>
              <th className="px-3 py-[3px] text-left font-normal">Filled At</th>
              <th className="px-3 py-[3px] text-left font-normal">Symbol</th>
              <th className="px-3 py-[3px] text-left font-normal">Side</th>
              <th className="px-3 py-[3px] text-right font-normal">Qty</th>
              <th className="px-3 py-[3px] text-right font-normal">Avg Price</th>
              <th className="px-3 py-[3px] text-right font-normal">Charges</th>
            </tr>
          </thead>
          <tbody>
            {portfolioLoading ? (
              <tr><td colSpan={6} className="py-12 text-center"><div className="flex items-center justify-center"><div className="h-5 w-5 rounded-full border-2 border-signal border-t-transparent animate-spin" /></div></td></tr>
            ) : fills.length === 0 ? (
              <tr><td colSpan={6} className="py-12 text-center text-xs text-text-muted">No fills yet</td></tr>
            ) : (
              fills.map((order) => (
                <tr key={order.id} className="border-b border-border-secondary/40 hover:bg-bg-secondary/30">
                  <td className="px-3 py-1.5 text-text-muted">{order.filled_at ? new Date(order.filled_at).toLocaleString('en-IN') : '--'}</td>
                  <td className="px-3 py-1.5 text-text-primary">{order.symbol}</td>
                  <td className={`px-3 py-1.5 font-medium ${order.side === 'BUY' ? 'text-profit' : 'text-loss'}`}>{order.side}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">{order.quantity}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">{order.average_price?.toFixed(2) ?? '--'}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-secondary">{order.charges.toFixed(2)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
