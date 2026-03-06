import { Activity, BadgeIndianRupee, Shield, Wifi } from 'lucide-react'

import { useStore } from '../store/useStore'

export default function Header() {
  const {
    snapshot,
    wsStatus,
    portfolios,
    selectedPortfolioId,
    setSelectedPortfolioId,
    funds,
    user,
  } = useStore()

  const selectedPortfolio = portfolios.find((item) => item.id === selectedPortfolioId)
  const totalEquity = funds?.total_equity ?? selectedPortfolio?.total_equity ?? 0
  const realizedPnl = funds?.realized_pnl ?? selectedPortfolio?.realized_pnl ?? 0
  const pnlClass = realizedPnl >= 0 ? 'text-profit' : 'text-loss'

  return (
    <header className="fixed inset-x-0 top-0 z-40 flex h-14 items-center border-b border-border-primary bg-bg-header px-4 pl-16">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-signal text-xs font-bold text-white">
            LT
          </div>
          <div>
            <div className="text-sm font-semibold text-text-primary">Lite Options Terminal</div>
            <div className="text-[11px] text-text-muted">Brand-safe, options-only practice desk</div>
          </div>
        </div>
        <div className="ml-4 flex items-center gap-2 rounded-full border border-border-primary bg-bg-secondary px-2.5 py-1 text-[11px] text-text-secondary">
          <Wifi size={12} className={wsStatus === 'connected' ? 'text-profit' : 'text-loss'} />
          {wsStatus.toUpperCase()}
        </div>
      </div>

      <div className="mx-6 flex items-center gap-6 text-xs">
        <div>
          <div className="text-text-muted">Spot</div>
          <div className="text-base font-semibold tabular-nums text-text-primary">
            {snapshot ? snapshot.spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
          </div>
        </div>
        <div>
          <div className="text-text-muted">Change</div>
          <div className={`tabular-nums ${snapshot && snapshot.change >= 0 ? 'text-profit' : 'text-loss'}`}>
            {snapshot ? `${snapshot.change >= 0 ? '+' : ''}${snapshot.change.toFixed(2)} (${snapshot.change_pct.toFixed(2)}%)` : '--'}
          </div>
        </div>
        <div>
          <div className="text-text-muted">VIX</div>
          <div className="tabular-nums text-text-primary">{snapshot?.vix?.toFixed(2) ?? '--'}</div>
        </div>
        <div>
          <div className="text-text-muted">PCR</div>
          <div className="tabular-nums text-text-primary">{snapshot?.pcr?.toFixed(2) ?? '--'}</div>
        </div>
        <div className="flex items-center gap-1 rounded-full border border-border-primary bg-bg-secondary px-2.5 py-1">
          <Activity size={12} className={snapshot?.market_status === 'OPEN' ? 'text-profit' : 'text-signal'} />
          <span className="text-[11px] text-text-secondary">{snapshot?.market_status ?? 'CLOSED'}</span>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-4">
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2">
          <div className="flex items-center gap-1 text-[11px] text-text-muted">
            <BadgeIndianRupee size={12} />
            Equity
          </div>
          <div className="tabular-nums text-sm font-semibold text-text-primary">
            {totalEquity.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2">
          <div className="text-[11px] text-text-muted">Realised P&amp;L</div>
          <div className={`tabular-nums text-sm font-semibold ${pnlClass}`}>
            {realizedPnl >= 0 ? '+' : ''}{realizedPnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </div>
        </div>
        <select
          value={selectedPortfolioId}
          onChange={(event) => setSelectedPortfolioId(event.target.value)}
          className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none"
        >
          {portfolios.map((portfolio) => (
            <option key={portfolio.id} value={portfolio.id}>{portfolio.name}</option>
          ))}
        </select>
        <div className="flex items-center gap-2 rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-sm">
          <Shield size={14} className="text-signal" />
          <div>
            <div className="text-text-primary">{user?.display_name ?? 'Guest'}</div>
            <div className="text-[11px] uppercase text-text-muted">{user?.role ?? 'viewer'}</div>
          </div>
        </div>
      </div>
    </header>
  )
}
