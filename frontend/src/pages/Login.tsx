import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { login, signup } from '../lib/api'
import { useStore } from '../store/useStore'

export default function Login() {
  const navigate = useNavigate()
  const { addToast } = useStore()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const isSignup = mode === 'signup'

  return (
    <div className="flex h-screen items-center justify-center bg-bg-primary">
      <div className="w-full mx-4 max-w-[360px] rounded-sm border border-border-primary bg-bg-secondary px-8 py-8">
        <div className="mb-8 flex flex-col items-center">
          <div className="text-[20px] font-light tracking-[0.3em] text-text-primary">lite</div>
          <h1 className="text-[13px] text-text-muted font-normal mt-1">
            {isSignup ? 'Create account' : 'Sign in'}
          </h1>
        </div>

        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault()
            setLoading(true)
            try {
              if (isSignup) {
                await signup(email, displayName, password)
                addToast('success', 'Account created')
              } else {
                await login(email, password)
                addToast('success', 'Signed in')
              }
              navigate('/')
            } catch (error) {
              addToast('error', error instanceof Error ? error.message : `${isSignup ? 'Signup' : 'Login'} failed`)
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
          {isSignup && (
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Display name"
              className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-signal"
            />
          )}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-signal"
          />
          <button
            type="submit"
            disabled={loading || !email || !password || (isSignup && !displayName)}
            className="w-full rounded-sm bg-signal py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {loading
              ? (isSignup ? 'Creating account\u2026' : 'Signing in\u2026')
              : (isSignup ? 'Sign up' : 'Login')
            }
          </button>
        </form>

        <p className="mt-5 text-center text-[12px] text-text-muted">
          {isSignup ? 'Already have an account?' : "Don't have an account?"}{' '}
          <button
            type="button"
            onClick={() => setMode(isSignup ? 'login' : 'signup')}
            className="text-signal hover:underline"
          >
            {isSignup ? 'Sign in' : 'Sign up'}
          </button>
        </p>

        <p className="mt-4 text-center text-[11px] leading-4 text-text-muted">
          Paper trading terminal &mdash; not connected to any live broker
        </p>
      </div>
    </div>
  )
}
