import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Fingerprint } from 'lucide-react'
import { ApiError, login, signup, webauthnAuthenticate, webauthnAuthenticateOptions, webauthnClientError } from '../lib/api'
import { getPasskey, getWebAuthnErrorInfo, isWebAuthnDismissed, supportsWebAuthn } from '../lib/webauthn'
import { useStore } from '../store/useStore'
import Logo from '../components/Logo'

export default function Login() {
  const navigate = useNavigate()
  const addToast = useStore((state) => state.addToast)
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [hasPasskey, setHasPasskey] = useState(false)
  const [savedEmail, setSavedEmail] = useState('')
  const [passkeyActive, setPasskeyActive] = useState(false)

  const handlePasskeyLogin = async (emailToUse: string) => {
    setLoading(true)
    setPasskeyActive(true)
    try {
      const { options } = await webauthnAuthenticateOptions(emailToUse)
      const credential = await getPasskey(options)
      await webauthnAuthenticate(credential, emailToUse)
      addToast('success', 'Signed in')
      const pCount = parseInt(localStorage.getItem('login-count') ?? '0', 10)
      localStorage.setItem('login-count', String(pCount + 1))
      navigate('/')
    } catch (error) {
      setPasskeyActive(false)
      const { code, message } = getWebAuthnErrorInfo(error, 'Unable to sign in with fingerprint.')
      const shouldForgetPasskey =
        error instanceof ApiError &&
        (
          error.status === 404 ||
          (error.status === 401 && message.toLowerCase().includes('authentication failed'))
        )

      if (shouldForgetPasskey) {
        localStorage.removeItem('lite_passkey_email')
        setHasPasskey(false)
        setSavedEmail('')
        addToast('error', 'Fingerprint login is no longer available. Please sign in with password and enable it again.')
      } else if (!isWebAuthnDismissed(error)) {
        addToast('error', `Passkey: ${message}`)
      }

      if (!isWebAuthnDismissed(error)) {
        void webauthnClientError({ stage: 'authenticate', email: emailToUse, code, message }).catch(() => undefined)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const passkeyEmail = localStorage.getItem('lite_passkey_email')
    if (passkeyEmail && supportsWebAuthn()) {
      setHasPasskey(true)
      setSavedEmail(passkeyEmail)
      setEmail(passkeyEmail)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (mode === 'signup') {
        await signup(email, displayName, password)
        addToast('success', 'Account created')
      } else {
        await login(email, password)
        addToast('success', 'Signed in')
      }
      const count = parseInt(localStorage.getItem('login-count') ?? '0', 10)
      localStorage.setItem('login-count', String(count + 1))
      navigate('/')
    } catch (error) {
      addToast('error', error instanceof Error ? error.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-bg-primary">
      <div className="w-full mx-4 max-w-[380px] rounded-sm border border-border-primary bg-bg-secondary px-8 py-8">
        {/* Logo + Title */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <Logo size={40} />
          <div className="text-[20px] font-light tracking-[0.3em] text-text-primary">
            lite
          </div>
          <p className="text-[13px] text-text-muted">
            {mode === 'login' ? 'Sign in to your account' : 'Create your account'}
          </p>
        </div>

        {passkeyActive ? (
          <div className="flex flex-col items-center gap-4 py-6">
            <Fingerprint size={48} className="text-brand animate-pulse" />
            <p className="text-sm text-text-secondary">
              Confirm your fingerprint to sign in
            </p>
            <p className="text-[11px] text-text-muted">
              Signing in as {savedEmail}
            </p>
          </div>
        ) : (
          <>
            <form className="space-y-4" onSubmit={handleSubmit}>
              {hasPasskey && mode === 'login' && (
                <>
                  <button
                    type="button"
                    onClick={() => handlePasskeyLogin(savedEmail)}
                    disabled={loading}
                    className="w-full flex items-center justify-center gap-2 rounded-sm border border-border-primary bg-bg-primary py-2.5 text-sm font-medium text-text-primary transition-colors hover:bg-bg-hover disabled:opacity-40"
                  >
                    <Fingerprint size={18} />
                    Sign in with fingerprint
                  </button>
                  <div className="flex items-center gap-3 my-1">
                    <div className="flex-1 h-px bg-border-primary" />
                    <span className="text-[11px] text-text-muted">or</span>
                    <div className="flex-1 h-px bg-border-primary" />
                  </div>
                </>
              )}

              {mode === 'signup' && (
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Display name"
                  required
                  className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-brand"
                />
              )}

              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                autoFocus
                required
                className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-brand"
              />

              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Password"
                  required
                  className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 pr-10 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-brand"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              <button
                type="submit"
                disabled={loading || !email || !password || (mode === 'signup' && !displayName)}
                className="w-full rounded-sm bg-brand py-2.5 text-sm font-semibold text-bg-primary transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {loading
                  ? (mode === 'login' ? 'Signing in\u2026' : 'Creating account\u2026')
                  : (mode === 'login' ? 'Login' : 'Sign up')}
              </button>
            </form>

            <p className="mt-5 text-center text-[12px] text-text-muted">
              <button
                type="button"
                onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
                className="text-signal hover:underline"
              >
                {mode === 'login'
                  ? "Don't have an account? Sign up"
                  : 'Already have an account? Sign in'}
              </button>
            </p>
          </>
        )}

        <p className="mt-4 text-center text-[11px] leading-4 text-text-muted">
          Paper trading terminal &mdash; not connected to any live broker
        </p>
      </div>
    </div>
  )
}
