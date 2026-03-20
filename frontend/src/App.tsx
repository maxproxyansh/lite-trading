import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useShallow } from 'zustand/react/shallow'

import ErrorBoundary from './components/ErrorBoundary'
import { FiiDiiModal } from './components/FiiDiiModal'
import { GlobalMarketsModal } from './components/GlobalMarketsModal'
import Header from './components/Header'
import { KeyboardShortcutsModal } from './components/KeyboardShortcutsModal'
import { MacroCalendarModal } from './components/MacroCalendarModal'
import MobileNav from './components/MobileNav'
import OrderModal from './components/OrderModal'
import Sidebar from './components/Sidebar'
import Toast from './components/Toast'
import TriggeredAlertModal from './components/TriggeredAlertModal'
import useKeyboardShortcuts from './hooks/useKeyboardShortcuts'
import { useWebSocket } from './hooks/useWebSocket'
import {
  fetchAlerts,
  fetchAnalytics,
  fetchFunds,
  fetchLatestSignal,
  fetchMe,
  fetchOptionChain,
  fetchOrders,
  fetchPortfolios,
  fetchPositions,
  fetchSnapshot,
  refreshSession,
  webauthnRegisterOptions,
  webauthnRegister,
} from './lib/api'
import { supportsWebAuthn, createPasskey } from './lib/webauthn'
import Analytics from './pages/Analytics'
import Dashboard from './pages/Dashboard'
import Desk from './pages/Desk'
import Funds from './pages/Funds'
import History from './pages/History'
import Login from './pages/Login'
import Orders from './pages/Orders'
import Portfolio from './pages/Portfolio'
import Positions from './pages/Positions'
import Settings from './pages/Settings'
import Trading from './pages/Trading'
import { useStore } from './store/useStore'

function ProtectedLayout({ onOpenMacroCalendar, onOpenFiiDii, onOpenGlobalMarkets }: { onOpenMacroCalendar: () => void; onOpenFiiDii: () => void; onOpenGlobalMarkets: () => void }) {
  const { user, spot } = useStore(useShallow((state) => ({
    user: state.user,
    spot: state.snapshot?.spot ?? null,
  })))
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
      '/trading': 'Trading',
      '/portfolio': 'Portfolio',
      '/desk': 'Desk',
    }
    const page = titles[location.pathname] ?? 'Dashboard'
    const prefix = spot && spot > 0
      ? `${spot.toLocaleString('en-IN')} — `
      : ''
    document.title = `${prefix}${page} — Lite`
  }, [location.pathname, spot])

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return (
    <ErrorBoundary>
      <div className="flex h-dvh flex-col bg-bg-primary text-text-primary">
        <Header />
        <div className="flex flex-1 overflow-hidden pb-14 md:pb-0">
          <Sidebar onOpenMacroCalendar={onOpenMacroCalendar} onOpenFiiDii={onOpenFiiDii} onOpenGlobalMarkets={onOpenGlobalMarkets} />
          <main className="md:ml-10 flex-1 overflow-auto animate-fade-in" key={location.pathname}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/positions" element={<Positions />} />
              <Route path="/orders" element={<Orders />} />
              <Route path="/history" element={<History />} />
              <Route path="/funds" element={<Funds />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/trading" element={<Trading />} />
              <Route path="/portfolio" element={<Portfolio />} />
              <Route path="/desk" element={<Desk />} />
            </Routes>
          </main>
        </div>
        <MobileNav />
        <TriggeredAlertModal />
        <OrderModal />
      </div>
    </ErrorBoundary>
  )
}

export default function App() {
  useWebSocket()
  const {
    shortcutsModalOpen, setShortcutsModalOpen,
    macroCalendarOpen, setMacroCalendarOpen,
    fiiDiiOpen, setFiiDiiOpen,
    globalMarketsOpen, setGlobalMarketsOpen,
  } = useKeyboardShortcuts()
  const navigate = useNavigate()
  const {
    accessToken,
    user,
    portfoliosLoaded,
    selectedPortfolioId,
    selectedExpiry,
    portfolioRefreshNonce,
    setSession,
    setSnapshot,
    setChain,
    setPortfolios,
    setOrders,
    setPositions,
    setFunds,
    setAnalytics,
    setAlerts,
    setLatestSignal,
    setSharedLoading,
    setPortfolioLoading,
    setChainLoading,
    addToast,
  } = useStore(useShallow((state) => ({
    accessToken: state.accessToken,
    user: state.user,
    portfoliosLoaded: state.portfoliosLoaded,
    selectedPortfolioId: state.selectedPortfolioId,
    selectedExpiry: state.selectedExpiry,
    portfolioRefreshNonce: state.portfolioRefreshNonce,
    setSession: state.setSession,
    setSnapshot: state.setSnapshot,
    setChain: state.setChain,
    setPortfolios: state.setPortfolios,
    setOrders: state.setOrders,
    setPositions: state.setPositions,
    setFunds: state.setFunds,
    setAnalytics: state.setAnalytics,
    setAlerts: state.setAlerts,
    setLatestSignal: state.setLatestSignal,
    setSharedLoading: state.setSharedLoading,
    setPortfolioLoading: state.setPortfolioLoading,
    setChainLoading: state.setChainLoading,
    addToast: state.addToast,
  })))

  // Auto-prompt passkey registration after login
  useEffect(() => {
    if (!user || !supportsWebAuthn()) return
    const passkeyEmail = localStorage.getItem('lite_passkey_email')
    if (passkeyEmail === user.email) return // Already registered

    const timer = setTimeout(async () => {
      try {
        const { options } = await webauthnRegisterOptions()
        const credential = await createPasskey(options)
        await webauthnRegister(credential)
        localStorage.setItem('lite_passkey_email', user.email)
        addToast('success', 'Fingerprint login enabled')
      } catch (err) {
        console.warn('[WebAuthn] Registration failed:', err)
      }
    }, 1500)

    return () => clearTimeout(timer)
  }, [user, addToast])

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
    if (!user) {
      return
    }

    let active = true

    async function loadShared() {
      setSharedLoading(true)
      try {
        const [portfolios, snapshot, signal] = await Promise.all([
          fetchPortfolios(),
          fetchSnapshot(),
          fetchLatestSignal(),
        ])
        if (!active) {
          return
        }
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
    if (!user || !portfoliosLoaded || !selectedPortfolioId) {
      return
    }

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
        if (!active) {
          return
        }
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
    const interval = window.setInterval(loadPortfolioViews, 30000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [
    addToast,
    portfolioRefreshNonce,
    portfoliosLoaded,
    selectedPortfolioId,
    setAnalytics,
    setFunds,
    setOrders,
    setPortfolioLoading,
    setPositions,
    user,
  ])

  useEffect(() => {
    if (!user) {
      return
    }

    let active = true

    async function loadChain() {
      setChainLoading(true)
      try {
        const chain = await fetchOptionChain(selectedExpiry ?? undefined)
        if (!active) {
          return
        }
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
    const interval = window.setInterval(loadChain, 30000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [addToast, selectedExpiry, setChain, setChainLoading, user])

  useEffect(() => {
    if (!user) {
      return
    }

    let active = true

    fetchAlerts()
      .then((alerts) => {
        if (active) {
          setAlerts(alerts)
        }
      })
      .catch((error) => {
        if (active) {
          addToast('error', error instanceof Error ? error.message : 'Failed to load alerts')
        }
      })

    return () => {
      active = false
    }
  }, [addToast, setAlerts, user])

  return (
    <>
      <Toast />
      {shortcutsModalOpen && <KeyboardShortcutsModal onClose={() => setShortcutsModalOpen(false)} />}
      {macroCalendarOpen && <MacroCalendarModal onClose={() => setMacroCalendarOpen(false)} />}
      {fiiDiiOpen && <FiiDiiModal onClose={() => setFiiDiiOpen(false)} />}
      {globalMarketsOpen && <GlobalMarketsModal onClose={() => setGlobalMarketsOpen(false)} />}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={
          <ProtectedLayout
            onOpenMacroCalendar={() => setMacroCalendarOpen(true)}
            onOpenFiiDii={() => setFiiDiiOpen(true)}
            onOpenGlobalMarkets={() => setGlobalMarketsOpen(true)}
          />
        } />
      </Routes>
    </>
  )
}
