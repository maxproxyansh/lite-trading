import LoadingState from '../components/LoadingState'
import { useStore } from '../store/useStore'

export default function Orders() {
  const { orders, portfolioLoading } = useStore()

  return (
    <div className="p-5">
      <h1 className="mb-4 text-base font-medium text-text-primary">Orders</h1>

      <table className="w-full text-xs">
        <thead className="border-b border-border-primary text-[11px] text-text-muted">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Time</th>
            <th className="px-3 py-2 text-left font-medium">Symbol</th>
            <th className="px-3 py-2 text-left font-medium">Side</th>
            <th className="px-3 py-2 text-left font-medium">Type</th>
            <th className="px-3 py-2 text-right font-medium">Qty</th>
            <th className="px-3 py-2 text-right font-medium">Price</th>
            <th className="px-3 py-2 text-right font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={7} className="p-0">
              <LoadingState loading={portfolioLoading} empty={orders.length === 0} emptyText="No orders yet">
                <table className="w-full text-xs">
                  <tbody>
                    {orders.map((order) => (
                      <tr key={order.id} className="border-b border-border-secondary/40 hover:bg-bg-secondary/30">
                        <td className="px-3 py-2.5 text-text-muted">{new Date(order.requested_at).toLocaleString('en-IN')}</td>
                        <td className="px-3 py-2.5 text-text-primary">{order.symbol}</td>
                        <td className={`px-3 py-2.5 font-medium ${order.side === 'BUY' ? 'text-profit' : 'text-loss'}`}>{order.side}</td>
                        <td className="px-3 py-2.5 text-text-secondary">{order.order_type}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-text-primary">{order.quantity}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-text-primary">{(order.average_price ?? order.price ?? 0).toFixed(2)}</td>
                        <td className="px-3 py-2.5 text-right text-text-secondary">{order.status}</td>
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
