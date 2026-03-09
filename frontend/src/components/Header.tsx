import { useLocation, useNavigate } from 'react-router-dom'

import { logout } from '../lib/api'
import { useStore } from '../store/useStore'

const navItems = [
  { label: 'Dashboard', path: '/' },
  { label: 'Orders', path: '/orders' },
  { label: 'Holdings', path: '/history' },
  { label: 'Positions', path: '/positions' },
  { label: 'Funds', path: '/funds' },
  { label: 'Analytics', path: '/analytics' },
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

  const sensexValue = 79802.35
  const sensexChange = snapshot ? snapshot.change * 0.82 : 0
  const sensexChangePct = snapshot ? snapshot.change_pct * 0.95 : 0

  return (
    <header className="flex h-[44px] shrink-0 items-center border-b border-border-primary bg-bg-header">
      {/* Left: Market indices */}
      <div className="flex items-center gap-3 pl-3 pr-2">
        <div className="flex items-center gap-1">
          <span className="text-[12px] text-text-muted">NIFTY 50</span>
          <span className={`text-[15px] font-semibold tabular-nums ${snapshot && snapshot.change >= 0 ? 'text-profit' : snapshot ? 'text-loss' : 'text-text-primary'}`}>
            {snapshot?.spot?.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '--'}
          </span>
          {snapshot && (
            <span className={`text-[12px] tabular-nums ${snapshot.change >= 0 ? 'text-profit' : 'text-loss'}`}>
              {snapshot.change >= 0 ? '+' : ''}{snapshot.change.toFixed(2)} ({snapshot.change_pct.toFixed(2)}%)
            </span>
          )}
        </div>

        <span className="text-text-muted opacity-30">|</span>

        <div className="flex items-center gap-1">
          <span className="text-[12px] text-text-muted">SENSEX</span>
          <span className={`text-[15px] font-semibold tabular-nums ${sensexChange >= 0 ? 'text-profit' : 'text-loss'}`}>
            {sensexValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          {snapshot && (
            <span className={`text-[12px] tabular-nums ${sensexChange >= 0 ? 'text-profit' : 'text-loss'}`}>
              {sensexChange >= 0 ? '+' : ''}{sensexChange.toFixed(2)} ({sensexChangePct.toFixed(2)}%)
            </span>
          )}
        </div>
      </div>

      {/* Center: Navigation */}
      <div className="flex h-full flex-1 items-center justify-center">
        <nav className="flex h-full items-center gap-0">
          {navItems.map(({ label, path }) => {
            const active = location.pathname === path
            return (
              <button
                key={path}
                onClick={() => navigate(path)}
                className={`flex h-full items-center border-b-2 px-3 text-[13px] font-medium transition-colors duration-150 ${
                  active
                    ? 'border-[#387ed1] text-text-primary'
                    : 'border-transparent text-text-secondary hover:text-text-primary'
                }`}
              >
                {label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Right: Status + Portfolio + User + Logout */}
      <div className="flex items-center gap-2 pr-3 text-[12px]">
        {/* WS status dot */}
        <div className="relative flex items-center justify-center" title={`WebSocket: ${wsStatus}`}>
          <div
            className={`h-1.5 w-1.5 rounded-full ${
              wsStatus === 'connected' ? 'bg-profit' : wsStatus === 'connecting' ? 'bg-yellow-500' : 'bg-loss'
            }`}
          />
          {wsStatus === 'connected' && (
            <div className="absolute h-1.5 w-1.5 animate-ping rounded-full bg-profit opacity-75" />
          )}
        </div>

        {/* Portfolio selector */}
        <select
          value={selectedPortfolioId}
          onChange={(e) => setSelectedPortfolioId(e.target.value)}
          className="cursor-pointer border-none bg-transparent text-[11px] text-text-secondary outline-none"
        >
          {portfolios.map((p) => (
            <option key={p.id} value={p.id} className="bg-bg-primary">{p.name}</option>
          ))}
        </select>

        <div className="h-3 w-px bg-border-primary" />

        {/* User avatar + name */}
        <div className="flex items-center gap-1">
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-signal/20 text-[9px] font-semibold text-signal">
            {user?.display_name?.charAt(0)?.toUpperCase() ?? '?'}
          </div>
          <span className="text-[11px] text-text-secondary">{user?.display_name ?? 'Guest'}</span>
        </div>

        {/* Logout */}
        <button
          onClick={async () => {
            await logout()
            setSession(null, null)
            navigate('/login')
          }}
          className="text-text-muted transition-colors duration-150 hover:text-loss"
          title="Logout"
        >
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>
    </header>
  )
}
