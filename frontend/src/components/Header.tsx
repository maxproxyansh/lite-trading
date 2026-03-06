import { useLocation, useNavigate } from 'react-router-dom'

import { logout } from '../lib/api'
import { useStore } from '../store/useStore'

const navItems = [
  { label: 'Terminal', path: '/' },
  { label: 'Positions', path: '/positions' },
  { label: 'Orders', path: '/orders' },
  { label: 'Tradebook', path: '/history' },
  { label: 'Funds', path: '/funds' },
  { label: 'Analytics', path: '/analytics' },
  { label: 'Settings', path: '/settings' },
]

export default function Header() {
  const navigate = useNavigate()
  const location = useLocation()
  const {
    snapshot,
    wsStatus,
    portfolios,
    selectedPortfolioId,
    setSelectedPortfolioId,
    user,
    setSession,
  } = useStore()

  return (
    <header className="flex h-12 shrink-0 items-center border-b border-border-primary bg-bg-primary">
      {/* Left: Market indices */}
      <div className="flex items-center gap-5 px-4 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-medium text-text-muted">NIFTY 50</span>
          <span className={`font-semibold tabular-nums ${snapshot && snapshot.change >= 0 ? 'text-profit' : snapshot ? 'text-loss' : 'text-text-primary'}`}>
            {snapshot?.spot?.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '--'}
          </span>
          {snapshot && (
            <span className={`tabular-nums ${snapshot.change >= 0 ? 'text-profit' : 'text-loss'}`}>
              {snapshot.change >= 0 ? '+' : ''}{snapshot.change.toFixed(2)} ({snapshot.change_pct.toFixed(2)}%)
            </span>
          )}
        </div>

        <div className="h-3.5 w-px bg-border-primary" />

        <div className="flex items-center gap-1.5">
          <span className="text-text-muted">VIX</span>
          <span className="tabular-nums text-text-primary">{snapshot?.vix?.toFixed(2) ?? '--'}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-text-muted">PCR</span>
          <span className="tabular-nums text-text-primary">{snapshot?.pcr?.toFixed(2) ?? '--'}</span>
        </div>
      </div>

      {/* Center: Logo + Navigation */}
      <div className="flex h-full items-center">
        <svg viewBox="0 0 24 24" className="mr-3 ml-2 h-5 w-5 text-signal">
          <path fill="currentColor" d="M12 2L4 12l8 10 8-10z"/>
        </svg>

        <nav className="flex h-full items-center">
          {navItems.map(({ label, path }) => {
            const active = location.pathname === path
            return (
              <button
                key={path}
                onClick={() => navigate(path)}
                className={`flex h-full items-center border-b-2 px-3 text-[13px] font-medium transition-colors ${
                  active
                    ? 'border-signal text-signal'
                    : 'border-transparent text-text-secondary hover:text-text-primary'
                }`}
              >
                {label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Right: Status + Portfolio + User */}
      <div className="ml-auto flex items-center gap-4 px-4 text-xs">
        <div
          className={`h-2 w-2 rounded-full ${
            wsStatus === 'connected' ? 'bg-profit' : wsStatus === 'connecting' ? 'bg-yellow-500' : 'bg-loss'
          }`}
          title={`WebSocket: ${wsStatus}`}
        />

        <select
          value={selectedPortfolioId}
          onChange={(e) => setSelectedPortfolioId(e.target.value)}
          className="cursor-pointer bg-transparent text-xs text-text-secondary outline-none"
        >
          {portfolios.map((p) => (
            <option key={p.id} value={p.id} className="bg-bg-secondary">{p.name}</option>
          ))}
        </select>

        <div className="h-3.5 w-px bg-border-primary" />

        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-bg-tertiary text-[10px] font-semibold text-text-secondary">
            {user?.display_name?.charAt(0)?.toUpperCase() ?? '?'}
          </div>
          <span className="text-text-secondary">{user?.display_name ?? 'Guest'}</span>
        </div>

        <button
          onClick={async () => {
            await logout()
            setSession(null, null)
            navigate('/login')
          }}
          className="text-text-muted transition-colors hover:text-loss"
          title="Logout"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>
    </header>
  )
}
