import { useStore } from '../store/useStore'
import { SkeletonTable } from '../components/Skeleton'
import { useShallow } from 'zustand/react/shallow'

export default function Orders() {
  const { orders, portfolioLoading } = useStore(useShallow((state) => ({
    orders: state.orders,
    portfolioLoading: state.portfolioLoading,
  })))

  if (portfolioLoading) return <SkeletonTable rows={8} cols={7} />

  return (
    <div>
      <div className="flex items-center justify-between border-b border-border-primary px-3 h-9">
        <h1 className="text-[12px] font-medium text-text-primary">Orders</h1>
      </div>

      {orders.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-text-muted">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" className="mb-4 opacity-30">
            <rect x="8" y="8" width="32" height="32" rx="1" stroke="currentColor" strokeWidth="1.5" />
            <line x1="16" y1="18" x2="32" y2="18" stroke="currentColor" strokeWidth="1.5" />
            <line x1="16" y1="24" x2="28" y2="24" stroke="currentColor" strokeWidth="1.5" />
            <line x1="16" y1="30" x2="24" y2="30" stroke="currentColor" strokeWidth="1.5" />
          </svg>
          <p className="text-sm">No orders yet</p>
          <p className="text-xs mt-1">Place your first order from the dashboard</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b border-border-primary">
              <tr>
                <th className="px-3 py-[3px] text-left font-normal text-xs text-text-muted uppercase tracking-wider">Time</th>
                <th className="px-3 py-[3px] text-left font-normal text-xs text-text-muted uppercase tracking-wider">Symbol</th>
                <th className="px-3 py-[3px] text-left font-normal text-xs text-text-muted uppercase tracking-wider w-16">Side</th>
                <th className="px-3 py-[3px] text-left font-normal text-xs text-text-muted uppercase tracking-wider w-16">Type</th>
                <th className="px-3 py-[3px] text-right font-normal text-xs text-text-muted uppercase tracking-wider w-20">Qty</th>
                <th className="px-3 py-[3px] text-right font-normal text-xs text-text-muted uppercase tracking-wider">Price</th>
                <th className="px-3 py-[3px] text-right font-normal text-xs text-text-muted uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id} className="border-b border-border-secondary/40 hover:bg-bg-hover transition-colors">
                  <td className="px-3 py-1.5 text-text-muted">{new Date(order.requested_at).toLocaleString('en-IN')}</td>
                  <td className="px-3 py-1.5 text-text-primary">{order.symbol}</td>
                  <td className={`px-3 py-1.5 font-medium ${order.side === 'BUY' ? 'text-profit' : 'text-loss'}`}>{order.side}</td>
                  <td className="px-3 py-1.5 text-text-secondary">{order.order_type}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">{order.quantity}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">{(order.average_price ?? order.price ?? 0).toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-right text-text-secondary">{order.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
