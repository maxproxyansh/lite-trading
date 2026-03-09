import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { login } from '../lib/api'
import { useStore } from '../store/useStore'

export default function Login() {
  const navigate = useNavigate()
  const { addToast } = useStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  return (
    <div className="flex h-screen items-center justify-center bg-bg-primary">
      <div className="w-full max-w-[360px] rounded-sm border border-border-primary bg-bg-secondary px-10 py-10">
        {/* Diamond Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <svg viewBox="0 0 24 28" className="h-10 w-8" style={{ color: '#e74c3c' }}>
            <path fill="currentColor" d="M12 0L0 12l12 6 12-6L12 0z" opacity="0.85" />
            <path fill="currentColor" d="M12 18L0 12l12 10 12-10-12 6z" />
          </svg>
          <h1 className="text-lg font-semibold tracking-tight text-text-primary">Login to Lite</h1>
        </div>

        <form
          className="space-y-4"
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
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            autoFocus
            className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-signal"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-signal"
          />
          <button
            type="submit"
            disabled={loading || !email || !password}
            className="w-full rounded-sm bg-signal py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {loading ? 'Signing in\u2026' : 'Login'}
          </button>
        </form>

        <p className="mt-6 text-center text-[11px] leading-4 text-text-muted">
          Paper trading terminal &mdash; not connected to any live broker
        </p>
      </div>
    </div>
  )
}
