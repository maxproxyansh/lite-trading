import { useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { login } from '../lib/api'
import { useStore } from '../store/useStore'

export default function Login() {
  const navigate = useNavigate()
  const { addToast } = useStore()
  const [email, setEmail] = useState('admin@lite.trade')
  const [password, setPassword] = useState('lite-admin-123')
  const [loading, setLoading] = useState(false)

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(255,107,53,0.18),_transparent_28%),linear-gradient(180deg,_#0b0d11,_#15171b_48%,_#0b0d11)] px-4">
      <div className="w-full max-w-md rounded-3xl border border-border-primary bg-[#111317]/95 p-8 shadow-2xl backdrop-blur">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-signal text-white">
            <ShieldCheck size={18} />
          </div>
          <div>
            <div className="text-lg font-semibold text-text-primary">Lite Options Terminal</div>
            <div className="text-sm text-text-muted">Private options practice desk</div>
          </div>
        </div>

        <div className="mb-5 rounded-2xl border border-border-primary bg-bg-primary p-3 text-xs leading-5 text-text-secondary">
          Broker-style UI, funds, margin, agent API keys and real-time market plumbing. Public signup is disabled.
        </div>

        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault()
            setLoading(true)
            try {
              await login(email, password)
              addToast('success', 'Signed in successfully')
              navigate('/')
            } catch (error) {
              addToast('error', error instanceof Error ? error.message : 'Login failed')
            } finally {
              setLoading(false)
            }
          }}
        >
          <label className="block text-sm text-text-secondary">
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 w-full rounded-2xl border border-border-primary bg-bg-primary px-4 py-3 text-text-primary outline-none" />
          </label>
          <label className="block text-sm text-text-secondary">
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 w-full rounded-2xl border border-border-primary bg-bg-primary px-4 py-3 text-text-primary outline-none" />
          </label>
          <button disabled={loading} className="w-full rounded-2xl bg-signal px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50">
            {loading ? 'Signing in…' : 'Enter Terminal'}
          </button>
        </form>
      </div>
    </div>
  )
}
