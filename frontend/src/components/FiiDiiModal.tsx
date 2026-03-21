import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { fetchParticipantsHistory } from '../lib/api'
import type { ParticipantPositions, ParticipantSnapshot } from '../lib/api'

type Participant = 'fii' | 'pro' | 'client'

const PARTICIPANTS: Participant[] = ['fii', 'pro', 'client']
const LABELS: Record<Participant, string> = { fii: 'FII', pro: 'PRO', client: 'Client' }
const GREEN = '#22c55e'
const RED = '#ef4444'
const AMBER = '#f59e0b'

function fmt(n: number): string {
  const abs = Math.abs(n)
  if (abs >= 10000000) return `${(n / 10000000).toFixed(1)}Cr`
  if (abs >= 100000) return `${(n / 100000).toFixed(1)}L`
  if (abs >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toLocaleString('en-IN')
}

function signed(n: number): string {
  return `${n >= 0 ? '+' : ''}${fmt(n)}`
}

function colorStd(n: number): string { return n > 0 ? GREEN : n < 0 ? RED : '#555' }
function colorPut(n: number): string { return n > 0 ? RED : n < 0 ? GREEN : '#555' }

function netCalls(p: ParticipantPositions): number { return p.opt_call_long - p.opt_call_short }
function netPuts(p: ParticipantPositions): number { return p.opt_put_long - p.opt_put_short }

function scoreFromPositions(nf: number, nc: number, np: number): number {
  const bullish = Math.max(0, nf) + Math.max(0, nc) + Math.max(0, -np)
  const bearish = Math.max(0, -nf) + Math.max(0, -nc) + Math.max(0, np)
  const total = bullish + bearish
  if (total === 0) return 0.5
  return bullish / total
}

function participantScore(p: ParticipantPositions): number {
  return scoreFromPositions(p.net_futures, netCalls(p), netPuts(p))
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
  const posScore = participantScore(data)
  if (!prev) return stanceLabel(posScore)
  const df = data.net_futures - prev.net_futures
  const dc = netCalls(data) - netCalls(prev)
  const dp = netPuts(data) - netPuts(prev)
  const actScore = scoreFromPositions(df, dc, dp)
  return stanceLabel(posScore * 0.6 + actScore * 0.4)
}

/* ── Metric cell ─────────────────────────────────────────────── */

function Metric({ label, value, change, colorFn }: {
  label: string; value: number; change: number | null; colorFn: (n: number) => string
}) {
  return (
    <div className="px-4 py-3">
      <div className="text-[9px] uppercase tracking-wider text-[#555] mb-1.5">{label}</div>
      <div className="font-mono text-[13px] leading-none" style={{ color: colorFn(value) }}>{signed(value)}</div>
      {change !== null && change !== 0 && (
        <div className="font-mono text-[9px] mt-1 leading-none" style={{ color: colorFn(change) }}>{signed(change)}</div>
      )}
    </div>
  )
}

/* ── Participant card ────────────────────────────────────────── */

function ParticipantCard({ label, data, prev }: { label: string; data: ParticipantPositions; prev: ParticipantPositions | null }) {
  const nf = data.net_futures
  const nc = netCalls(data)
  const np = netPuts(data)
  const chgF = prev ? nf - prev.net_futures : null
  const chgC = prev ? nc - netCalls(prev) : null
  const chgP = prev ? np - netPuts(prev) : null

  const stance = combinedStance(data, prev)
  const activity = prev ? activityLabel(data, prev) : null

  return (
    <div className="rounded-lg border border-[#252525] bg-[#161616]">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1e1e1e]">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-semibold text-[#e0e0e0]">{label}</span>
          {activity && (
            <span className="text-[9px]" style={{ color: activity.color }}>
              {activity.label}
            </span>
          )}
        </div>
        <span
          className="text-[10px] font-medium px-2 py-0.5 rounded"
          style={{ color: stance.color, background: `${stance.color}12`, border: `1px solid ${stance.color}20` }}
        >
          {stance.label}
        </span>
      </div>
      <div className="grid grid-cols-3 divide-x divide-[#1e1e1e]">
        <Metric label="Futures" value={nf} change={chgF} colorFn={colorStd} />
        <Metric label="Calls" value={nc} change={chgC} colorFn={colorStd} />
        <Metric label="Puts" value={np} change={chgP} colorFn={colorPut} />
      </div>
    </div>
  )
}

/* ── FII Long/Short Ratio chart ──────────────────────────────── */

function FiiLongShortRatio({ data }: { data: ParticipantSnapshot[] }) {
  const sorted = useMemo(
    () => [...data].sort((a, b) => a.date.localeCompare(b.date)),
    [data],
  )

  if (sorted.length < 3) return null

  // FII short % of total index futures OI (sum all participants)
  const ratios = sorted.map((s) => {
    const totalShort = s.fii.fut_short + s.dii.fut_short + s.pro.fut_short + s.client.fut_short
    if (totalShort === 0) return 50
    return (s.fii.fut_short / totalShort) * 100
  })

  const latest = ratios[ratios.length - 1]
  const min = Math.min(...ratios, 30)
  const max = Math.max(...ratios, 75)
  const range = max - min || 1

  // Chart dimensions
  const W = 100
  const H = 60
  const points = ratios
    .map((v, i) => {
      const x = (i / (ratios.length - 1)) * W
      const y = H - ((v - min) / range) * H
      return `${x},${y}`
    })
    .join(' ')

  // Y-axis ticks
  const yTicks = [40, 50, 60, 70].filter((t) => t >= min && t <= max)

  // Extreme zone (>65% = contrarian bullish signal)
  const extremeY = H - ((65 - min) / range) * H

  // Color: red if extreme (>65%), else neutral
  const lineColor = latest > 65 ? RED : latest > 55 ? AMBER : '#888'

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[10px] font-semibold uppercase tracking-[1px] text-[#555]">
          FII Short % of Index Futures OI
        </h3>
        <span className="font-mono text-[11px]" style={{ color: lineColor }}>
          {latest.toFixed(1)}%
        </span>
      </div>
      <div className="rounded-lg border border-[#252525] bg-[#161616] pl-8 pr-4 pt-3 pb-2 relative">
        {/* Y-axis labels */}
        <div className="absolute left-0 top-3 bottom-6 w-8 flex flex-col justify-between items-end pr-1.5">
          {[...yTicks].reverse().map((t) => (
            <span key={t} className="text-[8px] font-mono text-[#666] leading-none">{t}%</span>
          ))}
        </div>

        <svg viewBox={`-1 -4 ${W + 2} ${H + 8}`} className="w-full h-24" preserveAspectRatio="none">
          {/* Y grid lines */}
          {yTicks.map((t) => {
            const y = H - ((t - min) / range) * H
            return <line key={t} x1="0" y1={y} x2={W} y2={y} stroke="#1e1e1e" strokeWidth="0.3" />
          })}

          {/* Extreme zone line at 65% */}
          {65 >= min && 65 <= max && (
            <line x1="0" y1={extremeY} x2={W} y2={extremeY} stroke={RED} strokeWidth="0.3" strokeDasharray="2,1" opacity="0.4" />
          )}

          {/* Data line */}
          <polyline points={points} fill="none" stroke={lineColor} strokeWidth="1" vectorEffect="non-scaling-stroke" />
        </svg>

        {/* X-axis dates */}
        <div className="flex justify-between mt-1.5 text-[8px] text-[#666] font-mono">
          {(() => {
            const MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            const fmtDate = (d: string) => {
              const [, m, day] = d.split('-')
              return `${+day} ${MONTHS[+m]}`
            }
            const len = sorted.length
            const step = Math.max(1, Math.floor((len - 1) / 5))
            const indices: number[] = []
            for (let i = 0; i < len; i += step) indices.push(i)
            if (indices[indices.length - 1] !== len - 1) indices.push(len - 1)
            return indices.map((i) => <span key={i}>{fmtDate(sorted[i].date)}</span>)
          })()}
        </div>

        {/* Extreme zone label */}
        {latest > 65 && (
          <div className="mt-2 text-[9px] text-center" style={{ color: RED }}>
            Extreme short positioning — historically contrarian bullish
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Day view ────────────────────────────────────────────────── */

function DayView({ data, prev, history }: { data: ParticipantSnapshot; prev: ParticipantSnapshot | null; history: ParticipantSnapshot[] }) {
  return (
    <div className="p-5 space-y-5">
      {/* Participant cards */}
      <div className="space-y-3">
        {PARTICIPANTS.map((p) => (
          <ParticipantCard key={p} label={LABELS[p]} data={data[p]} prev={prev?.[p] ?? null} />
        ))}
      </div>

      <div className="border-t border-[#222]" />

      {/* FII Long/Short Ratio */}
      <FiiLongShortRatio data={history} />
    </div>
  )
}

/* ── Modal ────────────────────────────────────────────────────── */

interface Props {
  onClose: () => void
}

export const FiiDiiModal = memo(function FiiDiiModal({ onClose }: Props) {
  const [history, setHistory] = useState<ParticipantSnapshot[]>([])
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const sorted = useMemo(
    () => [...history].sort((a, b) => b.date.localeCompare(a.date)),
    [history],
  )

  const current = sorted[selectedIdx] ?? null
  const prev = sorted[selectedIdx + 1] ?? null
  const canGoNewer = selectedIdx > 0
  const canGoOlder = selectedIdx < sorted.length - 1

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchParticipantsHistory(60)
      setHistory(res.snapshots ?? [])
      setSelectedIdx(0)
    } catch {
      setError('Failed to load participant data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchData() }, [fetchData])

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onClose() }
      if (e.key === 'ArrowLeft' && canGoOlder) { setSelectedIdx((i) => i + 1); e.preventDefault() }
      if (e.key === 'ArrowRight' && canGoNewer) { setSelectedIdx((i) => i - 1); e.preventDefault() }
    }
    window.addEventListener('keydown', handleKey, true)
    return () => window.removeEventListener('keydown', handleKey, true)
  }, [onClose, canGoNewer, canGoOlder])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      <div
        className="relative w-[520px] max-w-[95vw] max-h-[85vh] flex flex-col rounded-xl border border-[#333] bg-[#1a1a1a] shadow-[0_24px_80px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#2a2a2a] bg-[#1a1a1a]/95 px-5 py-3 backdrop-blur-sm rounded-t-xl">
          <div>
            <h2 className="text-[14px] font-semibold text-[#e0e0e0]">FII / DII</h2>
            <p className="mt-0.5 text-[11px] text-[#666]">Participant-wise net positions</p>
          </div>
          <div className="flex items-center gap-2">
            {current && (
              <div className="flex items-center gap-1 mr-2">
                <button
                  onClick={() => canGoOlder && setSelectedIdx((i) => i + 1)}
                  disabled={!canGoOlder}
                  className="flex h-6 w-6 items-center justify-center rounded text-[#666] transition-colors hover:bg-[#2a2a2a] hover:text-[#ccc] disabled:opacity-30"
                >
                  <ChevronLeft size={14} />
                </button>
                <span className="text-[12px] text-[#e0e0e0] font-mono min-w-[80px] text-center">{current.date}</span>
                <button
                  onClick={() => canGoNewer && setSelectedIdx((i) => i - 1)}
                  disabled={!canGoNewer}
                  className="flex h-6 w-6 items-center justify-center rounded text-[#666] transition-colors hover:bg-[#2a2a2a] hover:text-[#ccc] disabled:opacity-30"
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            )}
            <button onClick={onClose} className="flex h-6 w-6 items-center justify-center rounded-md text-[#666] transition-colors hover:bg-[#2a2a2a] hover:text-[#ccc]">
              <X size={14} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#333] border-t-[#3b82f6]" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <p className="text-[12px] text-[#ef4444]">{error}</p>
              <button onClick={() => void fetchData()} className="text-[11px] text-[#3b82f6] hover:underline">Retry</button>
            </div>
          ) : !current ? (
            <div className="flex items-center justify-center py-20 text-[12px] text-[#666]">
              No data available — NSE publishes after market close
            </div>
          ) : (
            <DayView data={current} prev={prev} history={history} />
          )}
        </div>

        {sorted.length > 1 && (
          <div className="border-t border-[#222] px-5 py-2">
            <p className="text-center text-[10px] text-[#555]">
              <kbd className="inline-flex items-center justify-center min-w-[18px] h-[16px] px-1 rounded border border-[#444] bg-[#2a2a2a] font-mono text-[9px] text-[#ccc]">←</kbd>{' '}
              <kbd className="inline-flex items-center justify-center min-w-[18px] h-[16px] px-1 rounded border border-[#444] bg-[#2a2a2a] font-mono text-[9px] text-[#ccc]">→</kbd>{' '}
              navigate dates
            </p>
          </div>
        )}
      </div>
    </div>
  )
})
