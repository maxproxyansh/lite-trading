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
      <div className="w-full max-w-[420px] rounded border border-border-primary bg-bg-secondary/40 px-10 py-10">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <svg viewBox="0 0 32 32" className="h-12 w-12 text-signal">
            <path fill="currentColor" d="M8 16L16 4l8 12H8z" opacity="0.5"/>
            <path fill="currentColor" d="M8 16l8 12 8-12H8z"/>
          </svg>
          <span className="text-lg font-semibold tracking-tight text-text-primary">Login to Lite</span>
        </div>

        <form
          className="space-y-5"
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
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              autoFocus
              className="w-full rounded border border-border-primary bg-bg-primary px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-signal"
            />
          </div>
          <div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full rounded border border-border-primary bg-bg-primary px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-signal"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !email || !password}
            className="w-full rounded bg-signal py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
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
