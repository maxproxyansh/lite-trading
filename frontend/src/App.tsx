import { useEffect } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import ErrorBoundary from './components/ErrorBoundary'
import Header from './components/Header'
import MarketWatch from './components/MarketWatch'
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
    <ErrorBoundary>
      <div className="flex h-screen flex-col bg-bg-primary text-text-primary">
        <Header />
        <div className="flex flex-1 overflow-hidden">
          <MarketWatch />
          <main className="flex-1 overflow-auto">
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
        </div>
        <Toast />
      </div>
    </ErrorBoundary>
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
    setSharedLoading,
    setPortfolioLoading,
    setChainLoading,
    addToast,
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
      setSharedLoading(true)
      try {
        const [portfolios, snapshot, signal] = await Promise.all([
          fetchPortfolios(),
          fetchSnapshot(),
          fetchLatestSignal(),
        ])
        if (!active) return
        setPortfolios(portfolios)
        setSnapshot(snapshot)
        setLatestSignal(signal)
      } catch (error) {
        if (active) {
          addToast('error', error instanceof Error ? error.message : 'Failed to load market state')
        }
      } finally {
        if (active) {
          setSharedLoading(false)
        }
      }
    }
    void loadShared()
    const interval = window.setInterval(loadShared, 30000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [addToast, setLatestSignal, setPortfolios, setSharedLoading, setSnapshot, user])

  useEffect(() => {
    if (!user) return
    let active = true
    async function loadPortfolioViews() {
      setPortfolioLoading(true)
      try {
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
      } catch (error) {
        if (active) {
          addToast('error', error instanceof Error ? error.message : 'Failed to load portfolio views')
        }
      } finally {
        if (active) {
          setPortfolioLoading(false)
        }
      }
    }
    void loadPortfolioViews()
    const interval = window.setInterval(loadPortfolioViews, 10000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [addToast, selectedPortfolioId, setAnalytics, setFunds, setOrders, setPortfolioLoading, setPositions, user])

  useEffect(() => {
    if (!user) return
    let active = true
    async function loadChain() {
      setChainLoading(true)
      try {
        const chain = await fetchOptionChain(selectedExpiry ?? undefined)
        if (!active) return
        setChain(chain)
      } catch (error) {
        if (active) {
          addToast('error', error instanceof Error ? error.message : 'Failed to load option chain')
        }
      } finally {
        if (active) {
          setChainLoading(false)
        }
      }
    }
    void loadChain()
    const interval = window.setInterval(loadChain, 12000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [addToast, selectedExpiry, setChain, setChainLoading, user])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<ProtectedLayout />} />
    </Routes>
  )
}
