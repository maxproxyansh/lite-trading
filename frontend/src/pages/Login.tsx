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
      <div className="w-full mx-4 max-w-[360px] rounded-sm border border-border-primary bg-bg-secondary px-8 py-8">
        <div className="mb-8 flex flex-col items-center">
          <div className="text-[20px] font-light tracking-[0.3em] text-text-primary">lite</div>
          <h1 className="mt-1 text-[13px] font-normal text-text-muted">Sign in</h1>
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

        <p className="mt-5 text-center text-[12px] text-text-muted">
          Accounts are provisioned by an administrator.
        </p>

        <p className="mt-4 text-center text-[11px] leading-4 text-text-muted">
          Paper trading terminal &mdash; not connected to any live broker
        </p>
      </div>
    </div>
  )
}
