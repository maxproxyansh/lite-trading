import {
  BarChart2,
  History,
  LayoutDashboard,
  List,
  Settings,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: List, label: 'Orders', path: '/orders' },
  { icon: TrendingUp, label: 'Positions', path: '/positions' },
  { icon: History, label: 'History', path: '/history' },
  { icon: Wallet, label: 'Funds', path: '/funds' },
  { icon: BarChart2, label: 'Analytics', path: '/analytics' },
  { icon: Settings, label: 'Settings', path: '/settings' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <aside className="fixed left-0 top-11 z-20 flex h-[calc(100vh-2.75rem)] w-10 flex-col border-r border-border-primary bg-bg-sidebar">
      {navItems.map(({ icon: Icon, label, path }) => {
        const active = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
        return (
          <button
            key={path}
            onClick={() => navigate(path)}
            title={label}
            className={`flex h-10 w-full items-center justify-center border-l-2 transition-colors ${
              active
                ? 'border-[#387ed1] bg-bg-secondary text-signal'
                : 'border-transparent text-[#666] hover:bg-bg-secondary hover:text-text-primary'
            }`}
          >
            <Icon size={16} strokeWidth={1.5} />
          </button>
        )
      })}
    </aside>
  )
}
