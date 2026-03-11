import { useState } from 'react'
import { useShallow } from 'zustand/react/shallow'

import { createAgentKey, createUser } from '../lib/api'
import { useStore } from '../store/useStore'

export default function Settings() {
  const { user, addToast, selectedPortfolioId, portfolios } = useStore(useShallow((state) => ({
    user: state.user,
    addToast: state.addToast,
    selectedPortfolioId: state.selectedPortfolioId,
    portfolios: state.portfolios,
  })))
  const [agentKeyName, setAgentKeyName] = useState('trading-agent')
  const [newUserEmail, setNewUserEmail] = useState('')
  const [newUserName, setNewUserName] = useState('')
  const [newUserPassword, setNewUserPassword] = useState('')
  const [lastAgentSecret, setLastAgentSecret] = useState<string | null>(null)
  const selectedPortfolio = portfolios.find((item) => item.id === selectedPortfolioId) ?? null

  return (
    <div className="p-5">
      <h1 className="mb-5 text-base font-medium text-text-primary">Settings</h1>

      <div className="grid gap-5 xl:grid-cols-2">
        {/* Environment */}
        <div className="rounded bg-bg-secondary p-4">
          <div className="mb-3 text-xs font-medium text-text-secondary">Environment</div>
          <div className="space-y-2 text-xs text-text-muted">
            <div>Operator: <span className="text-text-primary">{user?.role ?? '--'}</span></div>
            <div>Signal source: <span className="text-text-primary">Server-configured</span></div>
          </div>
        </div>

        {/* Agent API Key */}
        <div className="rounded bg-bg-secondary p-4">
          <div className="mb-3 text-xs font-medium text-text-secondary">Create Agent API Key</div>
          <div className="flex gap-2">
            <input
              value={agentKeyName}
              onChange={(e) => setAgentKeyName(e.target.value)}
              className="flex-1 rounded border border-border-primary bg-bg-primary px-3 py-1.5 text-xs text-text-primary outline-none transition-colors focus:border-signal"
            />
            <button
              onClick={async () => {
                try {
                  if (!selectedPortfolio) {
                    addToast('error', 'Select a portfolio before generating an agent key')
                    return
                  }
                  const key = await createAgentKey(agentKeyName, selectedPortfolio.id, [
                    'orders:read',
                    'orders:write',
                    'positions:read',
                    'positions:write',
                    'signals:read',
                    'signals:write',
                    'funds:read',
                  ])
                  setLastAgentSecret(key.secret ?? null)
                  addToast('success', `Key generated for ${selectedPortfolio.name}`)
                } catch (error) {
                  addToast('error', error instanceof Error ? error.message : 'Failed to create key')
                }
              }}
              className="rounded bg-signal px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90"
            >
              Generate
            </button>
          </div>
          <div className="mt-2 text-[11px] text-text-muted">
            Bound portfolio: <span className="text-text-primary">{selectedPortfolio?.name ?? 'Select a portfolio'}</span>
          </div>
          {lastAgentSecret && (
            <div className="mt-3 rounded border border-border-primary bg-bg-primary p-3">
              <div className="mb-1 text-[11px] font-medium text-text-secondary">Agent secret</div>
              <div className="break-all font-mono text-[11px] text-text-primary">{lastAgentSecret}</div>
              <div className="mt-1 text-[10px] text-text-muted">This value is shown once. Store it in your agent runtime.</div>
            </div>
          )}
        </div>

        {user?.role === 'admin' && (
          <div className="rounded bg-bg-secondary p-4 xl:col-span-2">
            <div className="mb-3 text-xs font-medium text-text-secondary">Invite Operator</div>
            <div className="grid grid-cols-4 gap-2">
              <input
                value={newUserEmail}
                onChange={(e) => setNewUserEmail(e.target.value)}
                placeholder="email"
                className="rounded border border-border-primary bg-bg-primary px-3 py-1.5 text-xs text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-signal"
              />
              <input
                value={newUserName}
                onChange={(e) => setNewUserName(e.target.value)}
                placeholder="name"
                className="rounded border border-border-primary bg-bg-primary px-3 py-1.5 text-xs text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-signal"
              />
              <input
                type="password"
                value={newUserPassword}
                onChange={(e) => setNewUserPassword(e.target.value)}
                placeholder="password"
                className="rounded border border-border-primary bg-bg-primary px-3 py-1.5 text-xs text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-signal"
              />
              <button
                onClick={async () => {
                  try {
                    await createUser({ email: newUserEmail, display_name: newUserName, password: newUserPassword, role: 'trader' })
                    addToast('success', `Created ${newUserEmail}`)
                    setNewUserEmail('')
                    setNewUserName('')
                    setNewUserPassword('')
                  } catch (error) {
                    addToast('error', error instanceof Error ? error.message : 'Failed to create user')
                  }
                }}
                className="rounded bg-profit px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90"
              >
                Create
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
