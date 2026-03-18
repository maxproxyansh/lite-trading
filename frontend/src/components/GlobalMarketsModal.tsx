import { memo, useCallback, useEffect, useRef, useState } from 'react'

interface Props {
  onClose: () => void
}

interface GlobalQuote {
  ticker: string
  name: string
  group: string
  close: number | null
  change_pct: number | null
  change_abs: number | null
}

const GREEN = '#22c55e'
const RED = '#ef4444'
const NEUTRAL = '#888'

const ICONS: Record<string, { bg: string; bg2?: string; fg: string; label: string; border?: string }> = {
  'SP:SPX':        { bg: '#dc2626', bg2: '#991b1b', fg: '#fff', label: '500' },
  'NASDAQ:IXIC':   { bg: '#7c3aed', bg2: '#5b21b6', fg: '#fff', label: 'N', border: '#a78bfa33' },
  'DJ:DJI':        { bg: '#2563eb', bg2: '#1d4ed8', fg: '#fff', label: '30' },
  'NSE:NIFTY1!':   { bg: '#1e40af', bg2: '#1e3a8a', fg: '#60a5fa', label: 'N50', border: '#60a5fa33' },
  'FX:UKOIL':      { bg: '#292524', bg2: '#1c1917', fg: '#a3e635', label: 'OIL', border: '#a3e63533' },
  'TVC:GOLD':      { bg: 'linear-gradient(135deg, #f59e0b, #d97706)', fg: '#1a1a1a', label: 'G' },
  'TVC:US10Y':     { bg: '#1e3a5f', bg2: '#172554', fg: '#60a5fa', label: 'T10', border: '#60a5fa33' },
  'TVC:JP10Y':     { bg: '#fff', bg2: '#f0f0f0', fg: '#dc2626', label: 'J10', border: '#dc262633' },
  'TVC:DXY':       { bg: '#065f46', bg2: '#064e3b', fg: '#34d399', label: 'DX', border: '#34d39933' },
  'FX_IDC:USDINR': { bg: '#ea580c', bg2: '#c2410c', fg: '#fff', label: '₹' },
}

function fmt(n: number): string {
  if (Math.abs(n) >= 10000) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (Math.abs(n) >= 100) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (Math.abs(n) >= 1) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
}

function chgColor(n: number | null): string {
  if (n == null || n === 0) return NEUTRAL
  return n > 0 ? GREEN : RED
}

function SymbolIcon({ ticker }: { ticker: string }) {
  const icon = ICONS[ticker]
  if (!icon) return null
  const bgStyle = icon.bg.startsWith('linear')
    ? { backgroundImage: icon.bg }
    : icon.bg2
      ? { backgroundImage: `linear-gradient(145deg, ${icon.bg}, ${icon.bg2})` }
      : { background: icon.bg }
  return (
    <div
      className="flex items-center justify-center w-[28px] h-[28px] rounded-full shrink-0 text-[10px] font-extrabold leading-none tracking-tight shadow-sm"
      style={{
        ...bgStyle,
        color: icon.fg,
        border: icon.border ? `1.5px solid ${icon.border}` : undefined,
        textShadow: icon.fg === '#fff' ? '0 1px 2px rgba(0,0,0,0.3)' : undefined,
      }}
    >
      {icon.label}
    </div>
  )
}

function Row({ q, flash }: { q: GlobalQuote; flash: boolean }) {
  const c = chgColor(q.change_pct)
  return (
    <div className={`grid grid-cols-[28px_1fr_auto_auto_auto] items-center gap-x-3 px-4 py-[9px] border-b border-[#222] transition-colors ${flash ? 'bg-[#222]' : 'hover:bg-[#1e1e1e]'}`}>
      <SymbolIcon ticker={q.ticker} />
      <span className="text-[13px] text-[#e0e0e0] font-medium truncate">{q.name}</span>
      <span className="text-[13px] font-mono text-[#e0e0e0] text-right tabular-nums min-w-[82px]">
        {q.close != null ? fmt(q.close) : '—'}
      </span>
      <span className="text-[13px] font-mono text-right tabular-nums min-w-[70px]" style={{ color: c }}>
        {q.change_abs != null ? (q.change_abs >= 0 ? '+' : '') + fmt(q.change_abs) : '—'}
      </span>
      <span className="text-[13px] font-mono text-right tabular-nums min-w-[62px]" style={{ color: c }}>
        {q.change_pct != null ? (q.change_pct >= 0 ? '+' : '') + q.change_pct.toFixed(2) + '%' : '—'}
      </span>
    </div>
  )
}

export const GlobalMarketsModal = memo(function GlobalMarketsModal({ onClose }: Props) {
  const [quotes, setQuotes] = useState<GlobalQuote[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [flash, setFlash] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval>>(null)

  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    setError(null)
    try {
      const resp = await fetch('/api/v1/market/global', { credentials: 'include' })
      if (!resp.ok) throw new Error(`${resp.status}`)
      const data = await resp.json()
      setQuotes(data.quotes ?? [])
      if (silent) {
        setFlash(true)
        setTimeout(() => setFlash(false), 300)
      }
    } catch {
      if (!silent) setError('Failed to load global markets')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchData()
    intervalRef.current = setInterval(() => void fetchData(true), 30_000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [fetchData])

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onClose() }
    }
    window.addEventListener('keydown', handleKey, true)
    return () => window.removeEventListener('keydown', handleKey, true)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      <div
        className="relative w-[500px] max-w-[95vw] flex flex-col rounded-xl border border-[#333] bg-[#1a1a1a] shadow-[0_24px_80px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Column headers */}
        <div className="grid grid-cols-[28px_1fr_auto_auto_auto] items-center gap-x-3 px-4 py-2.5 border-b border-[#333] rounded-t-xl">
          <span />
          <span className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555]">Symbol</span>
          <span className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555] text-right min-w-[82px]">Last</span>
          <span className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555] text-right min-w-[70px]">Chg</span>
          <span className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555] text-right min-w-[62px]">Chg%</span>
        </div>

        {/* Rows */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#333] border-t-[#3b82f6]" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <p className="text-[12px] text-[#ef4444]">{error}</p>
            <button onClick={() => void fetchData()} className="text-[11px] text-[#3b82f6] hover:underline">Retry</button>
          </div>
        ) : (
          <div>
            {quotes.map((q) => (
              <Row key={q.ticker} q={q} flash={flash} />
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="px-4 py-2 border-t border-[#222] rounded-b-xl text-center">
          <span className="text-[9px] text-[#555]">Auto-refreshes every 30s · Esc to close</span>
        </div>
      </div>
    </div>
  )
})
