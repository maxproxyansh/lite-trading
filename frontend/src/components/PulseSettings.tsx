import { useEffect, useState } from 'react'
import { pulseStatus, pulseSetup, pulseDisconnect } from '../lib/api'

export default function PulseSettings() {
  const [connected, setConnected] = useState(false)
  const [keyPrefix, setKeyPrefix] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [claimToken, setClaimToken] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    pulseStatus()
      .then((s) => {
        setConnected(s.connected)
        setKeyPrefix(s.key_prefix)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleRegenerate = async () => {
    setBusy(true)
    try {
      const { claim_token, key_prefix } = await pulseSetup()
      setClaimToken(claim_token)
      setKeyPrefix(key_prefix)
    } catch {
      // silent
    } finally {
      setBusy(false)
    }
  }

  const handleDisconnect = async () => {
    setBusy(true)
    try {
      await pulseDisconnect()
      setConnected(false)
      setKeyPrefix(null)
      setClaimToken(null)
      localStorage.removeItem('pulse-connected')
    } catch {
      // silent
    } finally {
      setBusy(false)
    }
  }

  if (loading) return null

  return (
    <div className="rounded bg-bg-secondary p-4">
      <div className="mb-3 text-xs font-medium text-text-secondary">Lite Pulse</div>
      {connected ? (
        <div className="space-y-2 text-xs">
          <div className="text-text-muted">
            Status: <span className="text-profit">Connected</span>
          </div>
          {keyPrefix && (
            <div className="text-text-muted">
              Key: <span className="font-mono text-text-primary">{keyPrefix}***</span>
            </div>
          )}
          {claimToken && (
            <div className="mt-2 rounded border border-border-primary bg-bg-primary p-3">
              <div className="mb-1 text-[11px] font-medium text-text-secondary">Claim token</div>
              <input
                readOnly
                value={claimToken}
                onClick={(e) => (e.target as HTMLInputElement).select()}
                className="w-full break-all font-mono text-[11px] text-text-primary bg-transparent outline-none"
              />
            </div>
          )}
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleRegenerate}
              disabled={busy}
              className="rounded bg-signal px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              Regenerate
            </button>
            <button
              onClick={handleDisconnect}
              disabled={busy}
              className="rounded border border-border-primary px-3 py-1.5 text-xs text-text-muted transition-colors hover:text-loss hover:border-loss disabled:opacity-40"
            >
              Disconnect
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2 text-xs text-text-muted">
          <div>Status: Not connected</div>
          <div className="text-[11px]">Use the pulse icon in the header on mobile to set up.</div>
        </div>
      )}
    </div>
  )
}
