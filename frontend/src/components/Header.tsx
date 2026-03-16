import { useLocation, useNavigate } from 'react-router-dom'
import { useShallow } from 'zustand/react/shallow'

import { Keyboard } from 'lucide-react'

import Logo from '../components/Logo'
import { logout } from '../lib/api'
import { useStore } from '../store/useStore'

const navItems = [
  { label: 'Dashboard', path: '/' },
  { label: 'Orders', path: '/orders' },
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
    optionChartSymbol,
    setSelectedPortfolioId,
    setOptionChartSymbol,
    user,
  } = useStore(useShallow((state) => ({
    snapshot: state.snapshot,
    wsStatus: state.wsStatus,
    portfolios: state.portfolios,
    selectedPortfolioId: state.selectedPortfolioId,
    optionChartSymbol: state.optionChartSymbol,
    setSelectedPortfolioId: state.setSelectedPortfolioId,
    setOptionChartSymbol: state.setOptionChartSymbol,
    user: state.user,
  })))

  return (
    <header className="flex h-[44px] shrink-0 items-center border-b border-border-primary bg-bg-header">
      {/* Left: Logo + Market indices */}
      <div className="flex items-center gap-3 pl-3 pr-2">
        <div className="flex items-center gap-1.5">
          <Logo size={20} />
          <span className="text-[13px] font-semibold text-text-primary tracking-wide">lite</span>
        </div>
        <div
          className={`flex items-center gap-1 rounded px-1 py-0.5 transition-colors ${optionChartSymbol ? 'cursor-pointer hover:bg-bg-hover' : ''}`}
          onClick={optionChartSymbol ? () => setOptionChartSymbol(null) : undefined}
          title={optionChartSymbol ? 'Back to NIFTY chart' : undefined}
        >
          <span className="text-[12px] text-text-muted">NIFTY 50</span>
          <span className={`text-[15px] font-semibold tabular-nums ${snapshot && snapshot.spot > 0 && snapshot.change >= 0 ? 'text-profit' : snapshot && snapshot.spot > 0 ? 'text-loss' : 'text-text-primary'}`}>
            {snapshot && snapshot.spot > 0 ? snapshot.spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
          </span>
          {snapshot && snapshot.spot > 0 && (snapshot.change !== 0 || snapshot.change_pct !== 0) && (
            <span className={`text-[11px] md:text-[12px] tabular-nums ${snapshot.change >= 0 ? 'text-profit' : 'text-loss'}`}>
              {snapshot.change >= 0 ? '+' : ''}{snapshot.change.toFixed(2)} ({snapshot.change_pct.toFixed(2)}%)
            </span>
          )}
        </div>
      </div>

      {/* Center: Navigation — hidden on mobile */}
      <div className="hidden md:flex h-full flex-1 items-center justify-center">
        <nav className="flex h-full items-center gap-0">
          {navItems.map(({ label, path }) => {
            const active = location.pathname === path
            return (
              <button
                key={path}
                onClick={() => navigate(path)}
                className={`flex h-full items-center border-b-2 px-3 text-[13px] font-medium transition-colors duration-150 ${
                  active
                    ? 'border-brand text-brand'
                    : 'border-transparent text-text-secondary hover:text-text-primary'
                }`}
              >
                {label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Spacer on mobile when nav is hidden */}
      <div className="flex-1 md:hidden" />

      {/* Right: Status + Portfolio + User + Logout */}
      <div className="flex items-center gap-2 pr-3 text-[12px]">
        {/* WS status — only shown when NOT connected */}
        {wsStatus !== 'connected' && (
          <div className="flex items-center gap-1" title={`WebSocket: ${wsStatus}`}>
            <div
              className={`h-1.5 w-1.5 rounded-full ${
                wsStatus === 'connecting' ? 'bg-yellow-500' : 'bg-loss'
              }`}
            />
            <span className="text-[10px] text-yellow-500">
              {wsStatus === 'connecting' ? 'Connecting…' : 'Disconnected'}
            </span>
          </div>
        )}

        {/* Portfolio selector — hidden on mobile */}
        <select
          value={selectedPortfolioId}
          onChange={(e) => setSelectedPortfolioId(e.target.value)}
          className="cursor-pointer border-none bg-transparent text-[11px] text-text-secondary outline-none"
        >
          {portfolios.map((p) => (
            <option key={p.id} value={p.id} className="bg-bg-primary">{p.kind === 'manual' ? 'Manual' : p.kind === 'agent' ? 'Agent' : p.name}</option>
          ))}
        </select>

        <div className="hidden md:block h-3 w-px bg-border-primary" />

        {/* User avatar + name */}
        <div className="flex items-center gap-1">
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-brand/20 text-[9px] font-semibold text-brand">
            {user?.display_name?.charAt(0)?.toUpperCase() ?? '?'}
          </div>
          <span className="hidden md:inline text-[11px] text-text-secondary">{user?.display_name ?? 'Guest'}</span>
        </div>

        {/* Shortcuts help */}
        <button
          onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true }))}
          className="hidden md:flex items-center justify-center text-[#555] transition-colors hover:text-text-secondary"
          title="Keyboard shortcuts (?)"
        >
          <Keyboard size={14} />
        </button>

        {/* Logout */}
        <button
          onClick={async () => {
            try {
              await logout()
            } catch {
              // logout() clears local session state even when the network call fails.
            }
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
