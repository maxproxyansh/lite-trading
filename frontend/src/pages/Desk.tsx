import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { fetchGlobalMarkets, fetchParticipantsHistory } from '../lib/api'
import type { GlobalQuote, ParticipantSnapshot } from '../lib/api'

type Tab = 'calendar' | 'fiidii' | 'global'

export default function Desk() {
  const [tab, setTab] = useState<Tab>('fiidii')

  const tabs: { key: Tab; label: string }[] = [
    { key: 'fiidii', label: 'FII / DII' },
    { key: 'global', label: 'Global Markets' },
    { key: 'calendar', label: 'Macro Calendar' },
  ]

  return (
    <div className="flex h-full flex-col">
      {/* Sub-tabs */}
      <div className="flex border-b border-border-secondary">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex flex-1 items-center justify-center py-2 text-[11px] font-medium transition-colors ${
              tab === t.key ? 'border-b-2 border-brand text-brand' : 'text-text-muted'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {tab === 'calendar' ? <InlineMacroCalendar /> : tab === 'global' ? <InlineGlobalMarkets /> : <InlineFiiDii />}
      </div>
    </div>
  )
}

/* ── Inline Macro Calendar ───────────────────────────────────── */

function InlineMacroCalendar() {
  const [showAll, setShowAll] = useState(false)

  const config = {
    colorTheme: 'dark',
    isTransparent: true,
    width: '100%',
    height: '100%',
    importanceFilter: showAll ? '-1,0,1' : '0,1',
    countryFilter: 'in,us,eu,gb,jp,cn',
  }
  const src = `https://s.tradingview.com/embed-widget/events/?locale=en#${encodeURIComponent(JSON.stringify(config))}`

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-secondary">
        <span className="text-[11px] text-text-muted">Economic events & data releases</span>
        <button
          onClick={() => setShowAll((v) => !v)}
          className={`px-2 py-0.5 rounded text-[10px] transition-colors ${
            showAll ? 'bg-bg-tertiary text-text-muted' : 'bg-brand/15 text-brand'
          }`}
        >
          {showAll ? 'All events' : 'Important only'}
        </button>
      </div>
      <div className="flex-1 min-h-0">
        <iframe
          key={showAll ? 'all' : 'important'}
          src={src}
          className="w-full h-full border-0"
          title="Economic Calendar"
          sandbox="allow-scripts allow-same-origin allow-popups"
        />
      </div>
    </div>
  )
}

/* ── Inline FII/DII (reuses modal internals) ─────────────────── */

// Duplicating the core rendering from FiiDiiModal but without the modal chrome.
// We import the API types and reuse the same data fetching.

type Participant = 'fii' | 'pro' | 'client'
const PARTICIPANTS: Participant[] = ['fii', 'pro', 'client']
const LABELS: Record<Participant, string> = { fii: 'FII', pro: 'PRO', client: 'Client' }
const GREEN = '#22c55e'
const RED = '#ef4444'
const AMBER = '#f59e0b'

function fmt(n: number): string {
  const abs = Math.abs(n)
  if (abs >= 100000) return `${(n / 1000).toFixed(1)}K`
  if (abs >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toLocaleString('en-IN')
}
function signed(n: number): string { return `${n >= 0 ? '+' : ''}${fmt(n)}` }
function colorStd(n: number): string { return n > 0 ? GREEN : n < 0 ? RED : '#555' }
function colorPut(n: number): string { return n > 0 ? RED : n < 0 ? GREEN : '#555' }

import type { ParticipantPositions } from '../lib/api'

function netCalls(p: ParticipantPositions): number { return p.opt_call_long - p.opt_call_short }
function netPuts(p: ParticipantPositions): number { return p.opt_put_long - p.opt_put_short }

function scoreFromPositions(nf: number, nc: number, np: number): number {
  const bullish = Math.max(0, nf) + Math.max(0, nc) + Math.max(0, -np)
  const bearish = Math.max(0, -nf) + Math.max(0, -nc) + Math.max(0, np)
  const total = bullish + bearish
  return total === 0 ? 0.5 : bullish / total
}

type Stance = { label: string; color: string }

function stanceLabel(score: number): Stance {
  if (score >= 0.8) return { label: 'Very Bullish', color: GREEN }
  if (score >= 0.55) return { label: 'Bullish', color: GREEN }
  if (score > 0.45) return { label: 'Mixed', color: AMBER }
  if (score > 0.2) return { label: 'Bearish', color: RED }
  return { label: 'Very Bearish', color: RED }
}

function activityLabel(curr: ParticipantPositions, prev: ParticipantPositions): Stance {
  const df = curr.net_futures - prev.net_futures
  const dc = netCalls(curr) - netCalls(prev)
  const dp = netPuts(curr) - netPuts(prev)
  const bullish = Math.max(0, df) + Math.max(0, dc) + Math.max(0, -dp)
  const bearish = Math.max(0, -df) + Math.max(0, -dc) + Math.max(0, dp)
  const total = bullish + bearish
  if (total === 0) return { label: 'No change', color: '#555' }
  const score = bullish / total
  if (score >= 0.6) return { label: 'Adding longs', color: GREEN }
  if (score <= 0.4) return { label: 'Adding shorts', color: RED }
  return { label: 'Mixed activity', color: AMBER }
}

function combinedStance(data: ParticipantPositions, prev: ParticipantPositions | null): Stance {
  const posScore = scoreFromPositions(data.net_futures, netCalls(data), netPuts(data))
  if (!prev) return stanceLabel(posScore)
  const df = data.net_futures - prev.net_futures
  const dc = netCalls(data) - netCalls(prev)
  const dp = netPuts(data) - netPuts(prev)
  const actScore = scoreFromPositions(df, dc, dp)
  return stanceLabel(posScore * 0.6 + actScore * 0.4)
}

function InlineFiiDii() {
  const [history, setHistory] = useState<ParticipantSnapshot[]>([])
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [loading, setLoading] = useState(true)

  const sorted = useMemo(() => [...history].sort((a, b) => b.date.localeCompare(a.date)), [history])
  const current = sorted[selectedIdx] ?? null
  const prev = sorted[selectedIdx + 1] ?? null
  const canGoNewer = selectedIdx > 0
  const canGoOlder = selectedIdx < sorted.length - 1

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchParticipantsHistory(60)
      setHistory(res.snapshots ?? [])
      setSelectedIdx(0)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void fetchData() }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#333] border-t-[#3b82f6]" />
      </div>
    )
  }

  if (!current) {
    return <div className="flex items-center justify-center py-20 text-[12px] text-text-muted">No data available</div>
  }

  return (
    <div>
      {/* Date nav */}
      <div className="flex items-center justify-center gap-2 py-3 border-b border-border-secondary">
        <button onClick={() => canGoOlder && setSelectedIdx((i) => i + 1)} disabled={!canGoOlder}
          className="flex h-7 w-7 items-center justify-center rounded text-text-muted transition-colors hover:bg-bg-hover disabled:opacity-30">
          <ChevronLeft size={14} />
        </button>
        <span className="text-[12px] text-text-primary font-mono min-w-[80px] text-center">{current.date}</span>
        <button onClick={() => canGoNewer && setSelectedIdx((i) => i - 1)} disabled={!canGoNewer}
          className="flex h-7 w-7 items-center justify-center rounded text-text-muted transition-colors hover:bg-bg-hover disabled:opacity-30">
          <ChevronRight size={14} />
        </button>
      </div>

      {/* Cards */}
      <div className="p-4 space-y-3">
        {PARTICIPANTS.map((p) => {
          const data = current[p]
          const pv = prev?.[p] ?? null
          const nf = data.net_futures
          const nc = netCalls(data)
          const np = netPuts(data)
          const chgF = pv ? nf - pv.net_futures : null
          const chgC = pv ? nc - netCalls(pv) : null
          const chgP = pv ? np - netPuts(pv) : null
          const stance = combinedStance(data, pv)
          const activity = pv ? activityLabel(data, pv) : null

          return (
            <div key={p} className="rounded-lg border border-[#252525] bg-[#161616]">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1e1e1e]">
                <div className="flex items-center gap-2">
                  <span className="text-[12px] font-semibold text-[#e0e0e0]">{LABELS[p]}</span>
                  {activity && <span className="text-[9px]" style={{ color: activity.color }}>{activity.label}</span>}
                </div>
                <span className="text-[10px] font-medium px-2 py-0.5 rounded"
                  style={{ color: stance.color, background: `${stance.color}12`, border: `1px solid ${stance.color}20` }}>
                  {stance.label}
                </span>
              </div>
              <div className="grid grid-cols-3 divide-x divide-[#1e1e1e]">
                <MetricCell label="Futures" value={nf} change={chgF} colorFn={colorStd} />
                <MetricCell label="Calls" value={nc} change={chgC} colorFn={colorStd} />
                <MetricCell label="Puts" value={np} change={chgP} colorFn={colorPut} />
              </div>
            </div>
          )
        })}

        {/* FII Long/Short ratio chart */}
        <FiiRatioChart data={history} />
      </div>
    </div>
  )
}

function MetricCell({ label, value, change, colorFn }: { label: string; value: number; change: number | null; colorFn: (n: number) => string }) {
  return (
    <div className="px-3 py-2.5">
      <div className="text-[9px] uppercase tracking-wider text-[#555] mb-1">{label}</div>
      <div className="font-mono text-[12px] leading-none" style={{ color: colorFn(value) }}>{signed(value)}</div>
      {change !== null && change !== 0 && (
        <div className="font-mono text-[9px] mt-0.5 leading-none" style={{ color: colorFn(change) }}>{signed(change)}</div>
      )}
    </div>
  )
}

/* ── Inline Global Markets ──────────────────────────────────── */

const GLOBAL_ICONS: Record<string, { bg: string; bg2?: string; fg: string; label: string; border?: string }> = {
  'SP:SPX':        { bg: '#dc2626', bg2: '#991b1b', fg: '#fff', label: '500' },
  'DJ:DJI':        { bg: '#2563eb', bg2: '#1d4ed8', fg: '#fff', label: '30' },
  'NASDAQ:IXIC':   { bg: '#7c3aed', bg2: '#5b21b6', fg: '#fff', label: 'N', border: '#a78bfa33' },
  'NSE:NIFTY1!':   { bg: '#1e40af', bg2: '#1e3a8a', fg: '#60a5fa', label: 'N50', border: '#60a5fa33' },
  'FX:UKOIL':      { bg: '#292524', bg2: '#1c1917', fg: '#a3e635', label: 'OIL', border: '#a3e63533' },
  'TVC:GOLD':      { bg: 'linear-gradient(135deg, #f59e0b, #d97706)', fg: '#1a1a1a', label: 'G' },
  'TVC:US10Y':     { bg: '#1e3a5f', bg2: '#172554', fg: '#60a5fa', label: 'T10', border: '#60a5fa33' },
  'TVC:JP10Y':     { bg: '#fff', bg2: '#f0f0f0', fg: '#dc2626', label: 'J10', border: '#dc262633' },
  'TVC:DXY':       { bg: '#065f46', bg2: '#064e3b', fg: '#34d399', label: 'DX', border: '#34d39933' },
  'FX_IDC:USDINR': { bg: '#ea580c', bg2: '#c2410c', fg: '#fff', label: '₹' },
}

function globalFmt(n: number): string {
  if (Math.abs(n) >= 10000) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (Math.abs(n) >= 100) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (Math.abs(n) >= 1) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
}

function GlobalIcon({ ticker }: { ticker: string }) {
  const icon = GLOBAL_ICONS[ticker]
  if (!icon) return null
  const bgStyle = icon.bg.startsWith('linear')
    ? { backgroundImage: icon.bg }
    : icon.bg2
      ? { backgroundImage: `linear-gradient(145deg, ${icon.bg}, ${icon.bg2})` }
      : { background: icon.bg }
  return (
    <div
      className="flex items-center justify-center w-[28px] h-[28px] rounded-full shrink-0 text-[10px] font-extrabold leading-none tracking-tight shadow-sm"
      style={{ ...bgStyle, color: icon.fg, border: icon.border ? `1.5px solid ${icon.border}` : undefined, textShadow: icon.fg === '#fff' ? '0 1px 2px rgba(0,0,0,0.3)' : undefined }}
    >
      {icon.label}
    </div>
  )
}

function InlineGlobalMarkets() {
  const [quotes, setQuotes] = useState<GlobalQuote[]>([])
  const [loading, setLoading] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval>>(null)

  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const data = await fetchGlobalMarkets()
      setQuotes(data.quotes ?? [])
    } catch { /* ignore */ }
    finally { if (!silent) setLoading(false) }
  }, [])

  useEffect(() => {
    void fetchData()
    intervalRef.current = setInterval(() => void fetchData(true), 30_000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#333] border-t-[#3b82f6]" />
      </div>
    )
  }

  return (
    <div>
      <div className="grid grid-cols-[28px_1fr_auto_auto_auto] items-center gap-x-3 px-4 py-2 border-b border-[#333]">
        <span />
        <span className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555]">Symbol</span>
        <span className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555] text-right min-w-[72px]">Last</span>
        <span className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555] text-right min-w-[60px]">Chg</span>
        <span className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555] text-right min-w-[54px]">Chg%</span>
      </div>
      {quotes.map((q) => {
        const c = q.change_pct == null || q.change_pct === 0 ? '#888' : q.change_pct > 0 ? GREEN : RED
        return (
          <div key={q.ticker} className="grid grid-cols-[28px_1fr_auto_auto_auto] items-center gap-x-3 px-4 py-[9px] border-b border-[#222] hover:bg-[#1e1e1e] transition-colors">
            <GlobalIcon ticker={q.ticker} />
            <span className="text-[13px] text-[#e0e0e0] font-medium truncate">{q.name}</span>
            <span className="text-[13px] font-mono text-[#e0e0e0] text-right tabular-nums min-w-[72px]">{q.close != null ? globalFmt(q.close) : '—'}</span>
            <span className="text-[13px] font-mono text-right tabular-nums min-w-[60px]" style={{ color: c }}>{q.change_abs != null ? (q.change_abs >= 0 ? '+' : '') + globalFmt(q.change_abs) : '—'}</span>
            <span className="text-[13px] font-mono text-right tabular-nums min-w-[54px]" style={{ color: c }}>{q.change_pct != null ? (q.change_pct >= 0 ? '+' : '') + q.change_pct.toFixed(2) + '%' : '—'}</span>
          </div>
        )
      })}
      <div className="py-2 text-center">
        <span className="text-[9px] text-[#555]">Auto-refreshes every 30s</span>
      </div>
    </div>
  )
}

function FiiRatioChart({ data }: { data: ParticipantSnapshot[] }) {
  const sorted = useMemo(() => [...data].sort((a, b) => a.date.localeCompare(b.date)), [data])
  if (sorted.length < 3) return null

  const ratios = sorted.map((s) => {
    const totalShort = s.fii.fut_short + s.dii.fut_short + s.pro.fut_short + s.client.fut_short
    return totalShort === 0 ? 50 : (s.fii.fut_short / totalShort) * 100
  })

  const latest = ratios[ratios.length - 1]
  const min = Math.min(...ratios, 30)
  const max = Math.max(...ratios, 75)
  const range = max - min || 1
  const H = 60
  const W = 100
  const yTicks = [40, 50, 60, 70].filter((t) => t >= min && t <= max)
  const extremeY = H - ((65 - min) / range) * H
  const lineColor = latest > 65 ? RED : latest > 55 ? AMBER : '#888'
  const MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

  const points = ratios.map((v, i) => {
    const x = (i / (ratios.length - 1)) * W
    const y = H - ((v - min) / range) * H
    return `${x},${y}`
  }).join(' ')

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555]">FII Short % of Index Futures OI</span>
        <span className="font-mono text-[11px]" style={{ color: lineColor }}>{latest.toFixed(1)}%</span>
      </div>
      <div className="rounded-lg border border-[#252525] bg-[#161616] pl-8 pr-3 pt-3 pb-2 relative">
        <div className="absolute left-0 top-3 bottom-6 w-8 flex flex-col justify-between items-end pr-1.5">
          {[...yTicks].reverse().map((t) => (
            <span key={t} className="text-[8px] font-mono text-[#666] leading-none">{t}%</span>
          ))}
        </div>
        <svg viewBox={`-1 -4 ${W + 2} ${H + 8}`} className="w-full h-20" preserveAspectRatio="none">
          {yTicks.map((t) => {
            const y = H - ((t - min) / range) * H
            return <line key={t} x1="0" y1={y} x2={W} y2={y} stroke="#1e1e1e" strokeWidth="0.3" />
          })}
          {65 >= min && 65 <= max && (
            <line x1="0" y1={extremeY} x2={W} y2={extremeY} stroke={RED} strokeWidth="0.3" strokeDasharray="2,1" opacity="0.4" />
          )}
          <polyline points={points} fill="none" stroke={lineColor} strokeWidth="1" vectorEffect="non-scaling-stroke" />
        </svg>
        <div className="flex justify-between mt-1.5 text-[8px] text-[#666] font-mono">
          {(() => {
            const fmtDate = (d: string) => { const [, m, day] = d.split('-'); return `${+day} ${MONTHS[+m]}` }
            const len = sorted.length
            const step = Math.max(1, Math.floor((len - 1) / 4))
            const indices: number[] = []
            for (let i = 0; i < len; i += step) indices.push(i)
            if (indices[indices.length - 1] !== len - 1) indices.push(len - 1)
            return indices.map((i) => <span key={i}>{fmtDate(sorted[i].date)}</span>)
          })()}
        </div>
      </div>
    </div>
  )
}
