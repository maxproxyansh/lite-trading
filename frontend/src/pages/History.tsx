import { useStore } from '../store/useStore'

export default function History() {
  const { orders } = useStore()
  const fills = orders.filter((order) => order.status === 'FILLED')

  return (
    <div className="p-4">
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-text-primary">Tradebook</h1>
        <p className="text-sm text-text-muted">Filled option orders and executed prices.</p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-border-primary bg-bg-secondary">
        <table className="w-full text-sm">
          <thead className="bg-bg-primary text-text-muted">
            <tr>
              <th className="px-4 py-3 text-left">Filled At</th>
              <th className="px-4 py-3 text-left">Symbol</th>
              <th className="px-4 py-3 text-left">Side</th>
              <th className="px-4 py-3 text-right">Qty</th>
              <th className="px-4 py-3 text-right">Avg Price</th>
              <th className="px-4 py-3 text-right">Charges</th>
            </tr>
          </thead>
          <tbody>
            {fills.length === 0 ? (
              <tr><td className="px-4 py-12 text-center text-text-muted" colSpan={6}>No fills yet.</td></tr>
            ) : fills.map((order) => (
              <tr key={order.id} className="border-t border-border-primary/50">
                <td className="px-4 py-3 text-text-secondary">{order.filled_at ? new Date(order.filled_at).toLocaleString('en-IN') : '--'}</td>
                <td className="px-4 py-3 text-text-primary">{order.symbol}</td>
                <td className={`px-4 py-3 font-medium ${order.side === 'BUY' ? 'text-profit' : 'text-loss'}`}>{order.side}</td>
                <td className="px-4 py-3 text-right tabular-nums text-text-primary">{order.quantity}</td>
                <td className="px-4 py-3 text-right tabular-nums text-text-primary">{order.average_price?.toFixed(2) ?? '--'}</td>
                <td className="px-4 py-3 text-right tabular-nums text-text-primary">{order.charges.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
