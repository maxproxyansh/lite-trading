import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { login } from '../lib/api'
import { useStore } from '../store/useStore'

export default function Login() {
  const navigate = useNavigate()
  const { addToast } = useStore()
  const [email, setEmail] = useState('admin@lite.trade')
  const [password, setPassword] = useState('admin123')
  const [loading, setLoading] = useState(false)

  return (
    <div className="flex h-screen items-center justify-center bg-bg-primary">
      <div className="w-full max-w-[360px] px-6">
        {/* Logo */}
        <div className="mb-10 flex items-center justify-center gap-3">
          <svg viewBox="0 0 24 24" className="h-8 w-8 text-signal">
            <path fill="currentColor" d="M12 2L4 12l8 10 8-10z"/>
          </svg>
          <span className="text-xl font-semibold tracking-tight text-text-primary">Lite Options</span>
        </div>

        <form
          className="space-y-6"
          onSubmit={async (e) => {
            e.preventDefault()
            setLoading(true)
            try {
              await login(email, password)
              addToast('success', 'Signed in')
              navigate('/')
            } catch (error) {
              addToast('error', error instanceof Error ? error.message : 'Login failed')
            } finally {
              setLoading(false)
            }
          }}
        >
          <div>
            <label className="mb-1.5 block text-xs text-text-muted">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
              className="w-full border-b-2 border-border-primary bg-transparent py-2 text-sm text-text-primary outline-none transition-colors focus:border-signal"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs text-text-muted">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border-b-2 border-border-primary bg-transparent py-2 text-sm text-text-primary outline-none transition-colors focus:border-signal"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !email || !password}
            className="mt-2 w-full rounded bg-signal py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {loading ? 'Signing in\u2026' : 'Login'}
          </button>
        </form>

        <div className="mt-8 rounded border border-border-secondary bg-bg-secondary/50 px-4 py-3 text-center text-[11px] leading-5 text-text-muted">
          <span className="text-text-secondary">admin@lite.trade</span> / <span className="text-text-secondary">admin123</span>
          <br />Paper trading terminal &mdash; not connected to any live broker
        </div>
      </div>
    </div>
  )
}
