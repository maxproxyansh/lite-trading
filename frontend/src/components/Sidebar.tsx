import { BarChart3, BookOpen, CandlestickChart, CreditCard, LayoutDashboard, LogOut, Settings, ShieldCheck, Waves } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

import { logout } from '../lib/api'
import { useStore } from '../store/useStore'

const navItems = [
  { label: 'Terminal', path: '/', icon: LayoutDashboard },
  { label: 'Positions', path: '/positions', icon: CandlestickChart },
  { label: 'Orders', path: '/orders', icon: BookOpen },
  { label: 'Tradebook', path: '/history', icon: Waves },
  { label: 'Funds', path: '/funds', icon: CreditCard },
  { label: 'Analytics', path: '/analytics', icon: BarChart3 },
  { label: 'Settings', path: '/settings', icon: Settings },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { setSession } = useStore()

  return (
    <aside className="fixed inset-y-0 left-0 z-50 flex w-14 flex-col items-center border-r border-border-primary bg-bg-sidebar pt-3">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-signal to-btn-buy text-sm font-bold text-white">
        LO
      </div>
      <nav className="flex w-full flex-1 flex-col items-center gap-1">
        {navItems.map(({ label, path, icon: Icon }) => {
          const active = location.pathname === path
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              title={label}
              className={`flex h-10 w-10 items-center justify-center rounded-xl transition ${
                active ? 'bg-bg-tertiary text-text-primary' : 'text-text-muted hover:bg-bg-secondary hover:text-text-secondary'
              }`}
            >
              <Icon size={18} />
            </button>
          )
        })}
      </nav>
      <button
        onClick={async () => {
          await logout()
          setSession(null, null)
          navigate('/login')
        }}
        title="Logout"
        className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl text-text-muted transition hover:bg-bg-secondary hover:text-text-secondary"
      >
        <LogOut size={18} />
      </button>
      <div className="mb-4 flex items-center gap-1 rounded-full border border-border-primary bg-bg-secondary px-2 py-1 text-[10px] text-text-muted">
        <ShieldCheck size={10} className="text-profit" />
        private
      </div>
    </aside>
  )
}
