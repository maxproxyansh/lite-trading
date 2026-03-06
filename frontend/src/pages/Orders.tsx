import { useStore } from '../store/useStore'

export default function Orders() {
  const { orders } = useStore()

  return (
    <div className="p-4">
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-text-primary">Order Book</h1>
        <p className="text-sm text-text-muted">Pending, trigger-pending and filled single-leg option orders.</p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-border-primary bg-bg-secondary">
        <table className="w-full text-sm">
          <thead className="bg-bg-primary text-text-muted">
            <tr>
              <th className="px-4 py-3 text-left">Time</th>
              <th className="px-4 py-3 text-left">Symbol</th>
              <th className="px-4 py-3 text-left">Side</th>
              <th className="px-4 py-3 text-left">Type</th>
              <th className="px-4 py-3 text-right">Qty</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-4 py-3 text-right">Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr><td className="px-4 py-12 text-center text-text-muted" colSpan={7}>No orders yet.</td></tr>
            ) : orders.map((order) => (
              <tr key={order.id} className="border-t border-border-primary/50">
                <td className="px-4 py-3 text-text-secondary">{new Date(order.requested_at).toLocaleString('en-IN')}</td>
                <td className="px-4 py-3 text-text-primary">{order.symbol}</td>
                <td className={`px-4 py-3 font-medium ${order.side === 'BUY' ? 'text-profit' : 'text-loss'}`}>{order.side}</td>
                <td className="px-4 py-3 text-text-primary">{order.order_type}</td>
                <td className="px-4 py-3 text-right tabular-nums text-text-primary">{order.quantity}</td>
                <td className="px-4 py-3 text-right tabular-nums text-text-primary">{(order.average_price ?? order.price ?? 0).toFixed(2)}</td>
                <td className="px-4 py-3 text-right text-text-primary">{order.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
