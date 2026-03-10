import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { login, signup } from '../lib/api'
import { useStore } from '../store/useStore'
import Logo from '../components/Logo'

export default function Login() {
  const navigate = useNavigate()
  const { addToast } = useStore()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (mode === 'signup') {
        await signup(email, displayName, password)
        await login(email, password)
        addToast('success', 'Account created')
      } else {
        await login(email, password)
        addToast('success', 'Signed in')
      }
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

        <form className="space-y-4" onSubmit={handleSubmit}>
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

        <p className="mt-4 text-center text-[11px] leading-4 text-text-muted">
          Paper trading terminal &mdash; not connected to any live broker
        </p>
      </div>
    </div>
  )
}
