import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import ErrorBoundary from './components/ErrorBoundary'
import Header from './components/Header'
import MobileNav from './components/MobileNav'
import OptionsSidebarPanel from './components/OptionsSidebarPanel'
import Sidebar from './components/Sidebar'
import TradingViewTickerTape from './components/TradingViewTickerTape'
import OrderModal from './components/OrderModal'
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
  const { user, snapshot } = useStore()
  const location = useLocation()

  useEffect(() => {
    const titles: Record<string, string> = {
      '/': 'Dashboard',
      '/orders': 'Orders',
      '/positions': 'Positions',
      '/history': 'History',
      '/funds': 'Funds',
      '/analytics': 'Analytics',
      '/settings': 'Settings',
    }
    const page = titles[location.pathname] ?? 'Dashboard'
    const spotPrice = snapshot?.spot
    const prefix = spotPrice && spotPrice > 0
      ? `${spotPrice.toLocaleString('en-IN')} — `
      : ''
    document.title = `${prefix}${page} — Lite`
  }, [location.pathname, snapshot])

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return (
    <ErrorBoundary>
      <div className="flex h-screen flex-col bg-bg-primary text-text-primary">
        <Header />
        <div className="flex flex-1 overflow-hidden pb-14 md:pb-0">
          <Sidebar />
          <OptionsSidebarPanel />
          <main className="md:ml-10 flex-1 overflow-auto animate-fade-in" key={location.pathname}>
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
        <TradingViewTickerTape />
        <MobileNav />
        <Toast />
        <OrderModal />
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
    portfoliosLoaded,
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
    if (!user || !portfoliosLoaded || !selectedPortfolioId) return
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
  }, [addToast, portfoliosLoaded, selectedPortfolioId, setAnalytics, setFunds, setOrders, setPortfolioLoading, setPositions, user])

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
