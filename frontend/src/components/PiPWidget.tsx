// frontend/src/components/PiPWidget.tsx
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '../store/useStore'

export default function PiPWidget() {
  const { snapshot, wsStatus, positions } = useStore(
    useShallow((state) => ({
      snapshot: state.snapshot,
      wsStatus: state.wsStatus,
      positions: state.positions,
    }))
  )

  const spot = snapshot?.spot ?? 0
  const change = snapshot?.change ?? 0
  const changePct = snapshot?.change_pct ?? 0
  const isPositive = change >= 0
  const isStale = wsStatus !== 'connected'

  const showPnl = localStorage.getItem('pip-show-pnl') === 'true'
  const totalPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0)
  const hasPositions = positions.length > 0

  const pillClass = [
    'pip-pill',
    !isPositive && 'negative',
    isStale && 'stale',
  ].filter(Boolean).join(' ')

  return (
    <div className={pillClass}>
      <div className="pip-row">
        <span className="pip-label">NIFTY</span>
        <span className="pip-price">
          {spot > 0 ? spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
        </span>
        {spot > 0 && (
          <span className={`pip-change ${isPositive ? 'positive' : 'negative'}`}>
            {isPositive ? '+' : ''}{changePct.toFixed(2)}%
          </span>
        )}
      </div>
      {showPnl && hasPositions && (
        <div className="pip-row">
          <span className="pip-pnl-label">P&L</span>
          <span className={`pip-pnl-value ${totalPnl >= 0 ? 'positive' : 'negative'}`}>
            {totalPnl >= 0 ? '+' : ''}{'\u20B9'}{Math.abs(totalPnl).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
          </span>
        </div>
      )}
    </div>
  )
}
