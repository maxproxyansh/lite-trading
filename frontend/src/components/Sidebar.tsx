import {
  BarChart2,
  Grid2x2,
  History,
  LayoutDashboard,
  List,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { useStore } from '../store/useStore'

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: List, label: 'Orders', path: '/orders' },
  { icon: TrendingUp, label: 'Positions', path: '/positions' },
  { icon: History, label: 'History', path: '/history' },
  { icon: Wallet, label: 'Funds', path: '/funds' },
  { icon: BarChart2, label: 'Analytics', path: '/analytics' },
]

export default function Sidebar() {
  const { optionsSidebarOpen, toggleOptionsSidebar } = useStore()

  return (
    <aside className="fixed left-0 top-11 z-20 hidden md:flex h-[calc(100vh-2.75rem)] w-10 flex-col border-r border-border-primary bg-bg-sidebar">
      {navItems.map((item) => (
        <div key={item.path} className="group relative">
          <NavLink
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              `flex h-10 w-10 items-center justify-center border-l-[3px] transition-colors ${
                isActive
                  ? 'border-brand text-brand bg-bg-tertiary'
                  : 'border-transparent text-text-muted hover:text-text-secondary hover:bg-bg-hover'
              }`
            }
          >
            <item.icon size={18} strokeWidth={1.5} />
          </NavLink>
          <div className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 rounded-sm bg-bg-tertiary px-2 py-1 text-xs text-text-primary opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
            {item.label}
          </div>
        </div>
      ))}
      <div className="mt-auto">
        <div className="group relative">
          <button
            onClick={toggleOptionsSidebar}
            className={`flex h-10 w-10 items-center justify-center border-l-[3px] transition-colors ${
              optionsSidebarOpen
                ? 'border-brand text-brand bg-bg-tertiary'
                : 'border-transparent text-text-muted hover:text-text-secondary hover:bg-bg-hover'
            }`}
          >
            <Grid2x2 size={18} strokeWidth={1.5} />
          </button>
          <div className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 rounded-sm bg-bg-tertiary px-2 py-1 text-xs text-text-primary opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
            Options Chain
          </div>
        </div>
      </div>
    </aside>
  )
}
