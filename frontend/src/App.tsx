import { useEffect } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import Header from './components/Header'
import Sidebar from './components/Sidebar'
import Toast from './components/Toast'
import {
  fetchAnalytics,
  fetchLatestSignal,
  fetchMe,
  fetchOptionChain,
  fetchOrders,
  fetchPortfolios,
  fetchPositions,
  fetchFunds,
  fetchSnapshot,
  refreshSession,
} from './lib/api'
import { useWebSocket } from './hooks/useWebSocket'
import { useStore } from './store/useStore'
import Analytics from './pages/Analytics'
import Dashboard from './pages/Dashboard'
import Funds from './pages/Funds'
import History from './pages/History'
import Login from './pages/Login'
import Orders from './pages/Orders'
import Positions from './pages/Positions'
import Settings from './pages/Settings'

function ProtectedLayout() {
  const { user } = useStore()

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary">
      <Sidebar />
      <Header />
      <main className="min-h-screen pl-14 pt-14">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/positions" element={<Positions />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/history" element={<History />} />
          <Route path="/funds" element={<Funds />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
      <Toast />
    </div>
  )
}

export default function App() {
  useWebSocket()
  const navigate = useNavigate()
  const {
    accessToken,
    user,
    selectedPortfolioId,
    selectedExpiry,
    setSession,
    setSnapshot,
    setChain,
    setPortfolios,
    setOrders,
    setPositions,
    setFunds,
    setAnalytics,
    setLatestSignal,
  } = useStore()

  useEffect(() => {
    let active = true
    async function bootstrap() {
      if (!accessToken) {
        const ok = await refreshSession()
        if (!ok && active) {
          setSession(null, null)
        }
        return
      }
      try {
        const currentUser = await fetchMe()
        if (active) {
          setSession(accessToken, currentUser)
        }
      } catch {
        const ok = await refreshSession()
        if (!ok && active) {
          setSession(null, null)
          navigate('/login')
        }
      }
    }
    void bootstrap()
    return () => {
      active = false
    }
  }, [accessToken, navigate, setSession])

  useEffect(() => {
    if (!user) return
    let active = true
    async function loadShared() {
      const [portfolios, snapshot, signal] = await Promise.all([
        fetchPortfolios(),
        fetchSnapshot(),
        fetchLatestSignal(),
      ])
      if (!active) return
      setPortfolios(portfolios)
      setSnapshot(snapshot)
      setLatestSignal(signal)
    }
    void loadShared()
    const interval = window.setInterval(loadShared, 30000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [user, setLatestSignal, setPortfolios, setSnapshot])

  useEffect(() => {
    if (!user) return
    let active = true
    async function loadPortfolioViews() {
      const [orders, positions, funds, analytics] = await Promise.all([
        fetchOrders(selectedPortfolioId),
        fetchPositions(selectedPortfolioId),
        fetchFunds(selectedPortfolioId),
        fetchAnalytics(selectedPortfolioId),
      ])
      if (!active) return
      setOrders(orders)
      setPositions(positions)
      setFunds(funds)
      setAnalytics(analytics)
    }
    void loadPortfolioViews()
    const interval = window.setInterval(loadPortfolioViews, 10000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [user, selectedPortfolioId, setAnalytics, setFunds, setOrders, setPositions])

  useEffect(() => {
    if (!user) return
    let active = true
    async function loadChain() {
      const chain = await fetchOptionChain(selectedExpiry ?? undefined)
      if (!active) return
      setChain(chain)
    }
    void loadChain()
    const interval = window.setInterval(loadChain, 12000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [user, selectedExpiry, setChain])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<ProtectedLayout />} />
    </Routes>
  )
}
