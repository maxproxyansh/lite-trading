import { useState } from 'react'

import { createAgentKey, createUser } from '../lib/api'
import { useStore } from '../store/useStore'

export default function Settings() {
  const { user, addToast } = useStore()
  const [agentKeyName, setAgentKeyName] = useState('trading-agent')
  const [newUserEmail, setNewUserEmail] = useState('')
  const [newUserName, setNewUserName] = useState('')
  const [newUserPassword, setNewUserPassword] = useState('')

  return (
    <div className="grid gap-4 p-4 xl:grid-cols-2">
      <section className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
        <div className="mb-2 text-sm font-semibold text-text-primary">Environment</div>
        <div className="space-y-2 text-sm text-text-secondary">
          <div>Operator role: <span className="text-text-primary">{user?.role ?? '--'}</span></div>
          <div>Signal source: <span className="text-text-primary">Configured via server environment</span></div>
          <div>Preferred frontend slug: <span className="text-text-primary">lite-options-terminal</span></div>
          <div>Preferred backend slug: <span className="text-text-primary">lite-options-api</span></div>
        </div>
      </section>

      <section className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
        <div className="mb-2 text-sm font-semibold text-text-primary">Create Agent API Key</div>
        <div className="space-y-3">
          <input value={agentKeyName} onChange={(event) => setAgentKeyName(event.target.value)} className="w-full rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-text-primary outline-none" />
          <button
            onClick={async () => {
              try {
                const key = await createAgentKey(agentKeyName, ['orders:write', 'positions:read', 'positions:write', 'signals:read', 'funds:read'])
                addToast('success', `Generated key ${key.key_prefix} / secret ${key.secret}`)
              } catch (error) {
                addToast('error', error instanceof Error ? error.message : 'Failed to create API key')
              }
            }}
            className="rounded-xl bg-signal px-4 py-2 text-sm font-semibold text-white"
          >
            Generate Key
          </button>
        </div>
      </section>

      <section className="rounded-2xl border border-border-primary bg-bg-secondary p-4 xl:col-span-2">
        <div className="mb-2 text-sm font-semibold text-text-primary">Invite Human Operator</div>
        <div className="grid gap-3 md:grid-cols-4">
          <input value={newUserEmail} onChange={(event) => setNewUserEmail(event.target.value)} placeholder="email" className="rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-text-primary outline-none" />
          <input value={newUserName} onChange={(event) => setNewUserName(event.target.value)} placeholder="display name" className="rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-text-primary outline-none" />
          <input value={newUserPassword} onChange={(event) => setNewUserPassword(event.target.value)} placeholder="password" className="rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-text-primary outline-none" />
          <button
            onClick={async () => {
              try {
                await createUser({ email: newUserEmail, display_name: newUserName, password: newUserPassword, role: 'trader' })
                addToast('success', `Created user ${newUserEmail}`)
                setNewUserEmail('')
                setNewUserName('')
                setNewUserPassword('')
              } catch (error) {
                addToast('error', error instanceof Error ? error.message : 'Failed to create user')
              }
            }}
            className="rounded-xl bg-btn-buy px-4 py-2 text-sm font-semibold text-white"
          >
            Create User
          </button>
        </div>
      </section>
    </div>
  )
}
