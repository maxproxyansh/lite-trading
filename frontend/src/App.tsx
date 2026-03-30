import { useCallback, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Fingerprint } from 'lucide-react'
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
  webauthnClientError,
  webauthnRegisterOptions,
  webauthnRegister,
} from './lib/api'
import { createPasskey, getWebAuthnErrorInfo, isWebAuthnDismissed, supportsWebAuthn } from './lib/webauthn'
import type { EncodedRegistrationOptions } from './lib/webauthn'
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

  // Offer passkey registration after login
  const [showPasskeyPrompt, setShowPasskeyPrompt] = useState(false)
  const [passkeyRegisterOptions, setPasskeyRegisterOptions] = useState<EncodedRegistrationOptions | null>(null)
  const [passkeyPreparing, setPasskeyPreparing] = useState(false)
  const [passkeyEnabling, setPasskeyEnabling] = useState(false)

  const preparePasskeyRegistration = useCallback(async (email: string): Promise<boolean> => {
    setPasskeyPreparing(true)
    try {
      const { options } = await webauthnRegisterOptions()
      setPasskeyRegisterOptions(options)
      return true
    } catch (error) {
      const { code, message } = getWebAuthnErrorInfo(error, 'Unable to prepare fingerprint login.')
      console.warn('[WebAuthn] Failed to prepare registration:', code, message, error)
      void webauthnClientError({ stage: 'register', email, code, message }).catch(() => undefined)
      addToast('error', `Passkey: ${message}`)
      return false
    } finally {
      setPasskeyPreparing(false)
    }
  }, [addToast])

  useEffect(() => {
    if (!user || !supportsWebAuthn()) {
      setShowPasskeyPrompt(false)
      setPasskeyRegisterOptions(null)
      return
    }
    const passkeyEmail = localStorage.getItem('lite_passkey_email')
    if (passkeyEmail === user.email) {
      setShowPasskeyPrompt(false)
      setPasskeyRegisterOptions(null)
      return
    }

    let active = true
    const timer = setTimeout(() => {
      void preparePasskeyRegistration(user.email).then((ready) => {
        if (active && ready) {
          setShowPasskeyPrompt(true)
        }
      })
    }, 1500)

    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [user, preparePasskeyRegistration])

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
      {showPasskeyPrompt && (
        <div className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-50 w-[280px] rounded-lg border border-border-primary bg-bg-secondary shadow-[0_8px_32px_rgba(0,0,0,0.5)] overflow-hidden">
          <div className="px-4 pt-4 pb-3 flex flex-col items-center gap-2">
            <Fingerprint size={28} className="text-brand" />
            <p className="text-[13px] text-text-primary font-medium text-center">
              Enable fingerprint login
            </p>
            <p className="text-[11px] text-text-muted text-center leading-relaxed">
              Sign in instantly next time with your fingerprint
            </p>
          </div>
          <div className="flex border-t border-border-primary">
            <button
              onClick={() => setShowPasskeyPrompt(false)}
              className="flex-1 py-2.5 text-[12px] text-text-muted hover:text-text-secondary hover:bg-bg-hover transition-colors"
            >
              Skip
            </button>
            <div className="w-px bg-border-primary" />
            <button
              onClick={async () => {
                if (!user) return
                if (!passkeyRegisterOptions) {
                  addToast('error', 'Fingerprint setup is still preparing. Please tap Enable again in a moment.')
                  return
                }
                setPasskeyEnabling(true)
                try {
                  const credential = await createPasskey(passkeyRegisterOptions)
                  await webauthnRegister(credential)
                  localStorage.setItem('lite_passkey_email', user!.email)
                  setShowPasskeyPrompt(false)
                  setPasskeyRegisterOptions(null)
                  addToast('success', 'Fingerprint login enabled')
                } catch (err) {
                  const { code, message } = getWebAuthnErrorInfo(err, 'Unable to enable fingerprint login.')
                  console.warn('[WebAuthn] Registration failed:', code, message, err)
                  if (!isWebAuthnDismissed(err)) {
                    addToast('error', `Passkey: ${message}`)
                  }
                  void webauthnClientError({ stage: 'register', email: user.email, code, message }).catch(() => undefined)
                  void preparePasskeyRegistration(user.email)
                } finally {
                  setPasskeyEnabling(false)
                }
              }}
              disabled={passkeyPreparing || passkeyEnabling || !passkeyRegisterOptions}
              className="flex-1 py-2.5 text-[12px] font-medium text-brand hover:bg-bg-hover transition-colors disabled:opacity-40"
            >
              {passkeyEnabling ? 'Enabling...' : passkeyPreparing ? 'Preparing...' : 'Enable'}
            </button>
          </div>
        </div>
      )}
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
