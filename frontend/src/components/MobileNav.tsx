import {
  BarChart2,
  LayoutDashboard,
  List,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: List, label: 'Orders', path: '/orders' },
  { icon: TrendingUp, label: 'Positions', path: '/positions' },
  { icon: Wallet, label: 'Funds', path: '/funds' },
  { icon: BarChart2, label: 'Analytics', path: '/analytics' },
]

export default function MobileNav() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 flex h-14 border-t border-border-primary bg-bg-sidebar md:hidden">
      {navItems.map(({ icon: Icon, label, path }) => {
        const active = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
        return (
          <button
            key={path}
            onClick={() => navigate(path)}
            className={`flex flex-1 flex-col items-center justify-center gap-0.5 ${
              active ? 'text-brand' : 'text-text-muted'
            }`}
          >
            <Icon size={16} strokeWidth={1.5} />
            <span className="text-[10px]">{label}</span>
          </button>
        )
      })}
    </nav>
  )
}
