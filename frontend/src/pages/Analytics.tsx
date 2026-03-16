import { useEffect, useMemo, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'

import LoadingState from '../components/LoadingState'
import PnLHeatmap from '../components/PnLHeatmap'
import EquityCurveSVG from '../components/analytics/EquityCurveSVG'
import HBarChart from '../components/analytics/HBarChart'
import SlicePanel from '../components/analytics/SlicePanel'
import {
  sliceByOptionType, sliceByDirection, sliceByMoneyness, sliceByHoldDuration,
  sliceByDTE, sliceBySize, sliceByVixRegime, sliceByVixChange, sliceBySpotMove,
  sliceByDayOfWeek, sliceByTimeOfDay, sliceByExpiryWeek,
} from '../components/analytics/slicing'
import {
  detectRevengeTrades, detectOvertrading, analyzeConvictionSizing,
  analyzePremiumCapture, analyzeGapRisk,
} from '../components/analytics/behavioral'
import type { Trade } from '../components/analytics/types'
import type { BehavioralInsight } from '../components/analytics/behavioral'
import { fetchEnrichedAnalytics } from '../lib/api'
import type { EnrichedAnalyticsResponse } from '../lib/api'
import { useStore } from '../store/useStore'

/* ── Formatting helpers ── */

function fmt(v: number): string {
  return `\u20B9${Math.abs(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
function fmtCompact(v: number): string {
  const abs = Math.abs(v)
  if (abs >= 100000) return `\u20B9${(abs / 100000).toFixed(1)}L`
  if (abs >= 1000) return `\u20B9${(abs / 1000).toFixed(1)}K`
  return `\u20B9${abs.toFixed(0)}`
}
function fmtPnl(v: number): string {
  return `${v >= 0 ? '+' : '-'}${fmt(v)}`
}
function fmtPnlCompact(v: number): string {
  return `${v >= 0 ? '+' : '-'}${fmtCompact(v)}`
}
function cl(v: number): string {
  return v >= 0 ? 'text-profit' : 'text-loss'
}
function fmtHold(s: number): string {
  if (s < 60) return `${Math.round(s)}s`
  if (s < 3600) return `${Math.round(s / 60)}m`
  const h = Math.floor(s / 3600)
  const m = Math.round((s % 3600) / 60)
  if (h < 24) return m > 0 ? `${h}h ${m}m` : `${h}h`
  const d = Math.floor(h / 24)
  const rh = h % 24
  return rh > 0 ? `${d}d ${rh}h` : `${d}d`
}

/* ── MetricCol (FII/DII FUTURES/CALLS/PUTS pattern) ── */

function MetricCol({ label, value, sub, className = '' }: { label: string; value: string; sub?: string; className?: string }) {
  return (
    <div className="px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-text-muted mb-1.5">{label}</div>
      <div className={`text-[18px] font-semibold tabular-nums leading-none ${className}`}>{value}</div>
      {sub && <div className="text-[11px] text-text-muted mt-1.5 tabular-nums">{sub}</div>}
    </div>
  )
}

/* ── Badge (FII/DII Bearish/Bullish badge) ── */

function Badge({ label, variant }: { label: string; variant: 'profit' | 'loss' | 'neutral' }) {
  const cls = variant === 'profit'
    ? 'border-profit/40 text-profit'
    : variant === 'loss'
      ? 'border-loss/40 text-loss'
      : 'border-border-primary text-text-secondary'
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-sm border ${cls}`}>{label}</span>
  )
}

/* ── Main ── */

export default function Analytics() {
  const { analytics, portfolioLoading, selectedPortfolioId } = useStore(useShallow((s) => ({
    analytics: s.analytics,
    portfolioLoading: s.portfolioLoading,
    selectedPortfolioId: s.selectedPortfolioId,
  })))

  const [enriched, setEnriched] = useState<EnrichedAnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!selectedPortfolioId) return
    let active = true
    setLoading(true)
    fetchEnrichedAnalytics(selectedPortfolioId)
      .then((d) => { if (active) setEnriched(d) })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [selectedPortfolioId])

  /* ── Derived data ── */

  const equityCurve = useMemo(() =>
    (analytics?.equity_curve ?? [])
      .map((p) => ({ label: String(p.label ?? '').slice(0, 10), value: Number(p.value ?? 0) }))
      .filter((p) => /^\d{4}-\d{2}-\d{2}$/.test(p.label))
      .filter((p, i, a) => i === 0 || p.label !== a[i - 1].label),
    [analytics?.equity_curve],
  )

  const pnlByDay = useMemo(() =>
    (analytics?.pnl_by_day ?? []).map((p) => ({
      label: String(p.label ?? '').slice(0, 10),
      value: Number(p.value ?? 0),
    })),
    [analytics?.pnl_by_day],
  )

  const trades = useMemo<Trade[]>(() =>
    (enriched?.closed_trades ?? []) as unknown as Trade[],
    [enriched?.closed_trades],
  )

  const totalClosed = enriched?.total_closed_trades ?? 0
  const wins = trades.filter((t) => t.realized_pnl > 0)
  const losses = trades.filter((t) => t.realized_pnl < 0)
  const winRate = enriched?.win_rate ?? (analytics?.win_rate ?? 0)
  const expectancy = enriched?.expectancy ?? 0
  const riskReward = enriched?.risk_reward ?? 0
  const profitFactor = enriched?.profit_factor ?? 0
  const maxDD = enriched?.max_drawdown ?? 0
  const biggestWin = enriched?.biggest_win ?? 0
  const biggestLoss = enriched?.biggest_loss ?? 0
  const avgWinHold = enriched?.avg_win_hold_seconds ?? 0
  const avgLossHold = enriched?.avg_loss_hold_seconds ?? 0

  const recentDays = useMemo(() => [...pnlByDay].reverse().slice(0, 15), [pnlByDay])

  const insights = useMemo<BehavioralInsight[]>(() => {
    if (!trades.length) return []
    return [
      detectRevengeTrades(trades), detectOvertrading(trades),
      analyzeConvictionSizing(trades), analyzePremiumCapture(trades),
      analyzeGapRisk(trades),
    ].filter((x): x is BehavioralInsight => x !== null)
  }, [trades])

  const slicePanels = useMemo(() => {
    if (!trades.length) return []
    return [
      { title: 'By Type', rows: sliceByOptionType(trades) },
      { title: 'By Direction', rows: sliceByDirection(trades) },
      { title: 'By Moneyness', rows: sliceByMoneyness(trades) },
      { title: 'By Hold Duration', rows: sliceByHoldDuration(trades) },
      { title: 'By Days to Expiry', rows: sliceByDTE(trades) },
      { title: 'By Size', rows: sliceBySize(trades) },
      { title: 'By VIX Regime', rows: sliceByVixRegime(trades) },
      { title: 'By VIX Change', rows: sliceByVixChange(trades) },
      { title: 'By Spot Move', rows: sliceBySpotMove(trades) },
      { title: 'By Day of Week', rows: sliceByDayOfWeek(trades) },
      { title: 'By Time of Day', rows: sliceByTimeOfDay(trades) },
      { title: 'By Expiry Week', rows: sliceByExpiryWeek(trades) },
    ].filter((p) => p.rows.length > 0 && !(p.rows.length === 1 && p.rows[0].label === 'Unknown'))
  }, [trades])

  // Edge verdict
  const edgeLabel = profitFactor >= 1.5 ? 'Strong edge' : profitFactor >= 1 ? 'Marginal' : profitFactor > 0 ? 'No edge' : ''
  const edgeVariant: 'profit' | 'loss' | 'neutral' = profitFactor >= 1.5 ? 'profit' : profitFactor >= 1 ? 'neutral' : 'loss'

  // Hold behavior verdict
  const holdVerdict = avgWinHold > 0 && avgLossHold > 0
    ? avgWinHold > avgLossHold ? 'Letting winners run' : 'Cutting winners short'
    : ''
  const holdVariant: 'profit' | 'loss' = avgWinHold >= avgLossHold ? 'profit' : 'loss'

  const isLoading = (portfolioLoading || loading) && !analytics

  return (
    <div>
      {/* Page header */}
      <div className="flex items-center justify-between border-b border-border-primary px-3 h-9">
        <h1 className="text-[12px] font-medium text-text-primary">Analytics</h1>
        {totalClosed > 0 && <span className="text-[11px] text-text-muted tabular-nums">{totalClosed} trades</span>}
      </div>

      <div className="p-4 space-y-4 overflow-y-auto" style={{ height: 'calc(100vh - 36px)' }}>
        <LoadingState loading={isLoading} empty={false} emptyText="">

          {/* Section 1 — Performance Card */}
          <div className="rounded border border-border-primary">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border-primary">
              <div className="flex items-center gap-2">
                <span className="text-[14px] font-semibold text-text-primary">Performance</span>
                {totalClosed > 0 && (
                  <span className="text-[11px] text-text-muted">{wins.length}W / {losses.length}L</span>
                )}
              </div>
              {edgeLabel && <Badge label={edgeLabel} variant={edgeVariant} />}
            </div>
            <div className="grid grid-cols-4 divide-x divide-border-secondary">
              <MetricCol
                label="Net P&L"
                value={analytics ? fmtPnlCompact(analytics.realized_pnl) : '\u2014'}
                sub={analytics ? `Unrealised ${fmtPnlCompact(analytics.unrealized_pnl)}` : undefined}
                className={analytics ? cl(analytics.realized_pnl) : 'text-text-primary'}
              />
              <MetricCol
                label="Win Rate"
                value={totalClosed ? `${winRate.toFixed(1)}%` : '\u2014'}
                sub={totalClosed ? `${wins.length}W / ${losses.length}L` : undefined}
                className={totalClosed ? cl(winRate >= 50 ? 1 : -1) : 'text-text-primary'}
              />
              <MetricCol
                label="Expectancy"
                value={expectancy ? fmtPnlCompact(expectancy) : '\u2014'}
                sub="Per trade"
                className={expectancy ? cl(expectancy) : 'text-text-primary'}
              />
              <MetricCol
                label="Risk : Reward"
                value={riskReward ? `1 : ${riskReward.toFixed(2)}` : '\u2014'}
                sub={profitFactor ? `Factor ${profitFactor.toFixed(2)}` : undefined}
                className="text-text-primary"
              />
            </div>
          </div>

          {/* Section 2 — Equity Curve */}
          <div className="rounded border border-border-primary p-4 mt-4">
            <div className="text-[10px] uppercase tracking-wider text-text-muted mb-3">Equity Curve</div>
            <EquityCurveSVG data={equityCurve} height={140} />
          </div>

          {/* Section 3 — P&L Heatmap */}
          <div className="rounded border border-border-primary p-4 mt-4">
            <div className="text-[10px] uppercase tracking-wider text-text-muted mb-3">P&amp;L Heatmap</div>
            <PnLHeatmap data={analytics?.pnl_by_day ?? []} />
          </div>

          {/* Section 4 — Edge + Risk + Behavior (3 cards) */}
          <div className="grid grid-cols-3 gap-4 mt-4">
            {/* Your Edge */}
            <div className="rounded border border-border-primary">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-primary">
                <span className="text-[13px] font-semibold text-text-primary">Your Edge</span>
              </div>
              <div className="grid grid-cols-2 divide-x divide-border-secondary">
                <MetricCol
                  label="Risk : Reward"
                  value={riskReward ? `1 : ${riskReward.toFixed(1)}` : '\u2014'}
                  className={riskReward >= 1 ? 'text-profit' : riskReward > 0 ? 'text-loss' : 'text-text-primary'}
                />
                <MetricCol
                  label="Profit Factor"
                  value={profitFactor ? profitFactor.toFixed(2) : '\u2014'}
                  className={profitFactor >= 1.5 ? 'text-profit' : profitFactor >= 1 ? 'text-text-primary' : profitFactor > 0 ? 'text-loss' : 'text-text-primary'}
                />
              </div>
            </div>

            {/* Risk */}
            <div className="rounded border border-border-primary">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-primary">
                <span className="text-[13px] font-semibold text-text-primary">Risk</span>
              </div>
              <div className="grid grid-cols-3 divide-x divide-border-secondary">
                <MetricCol label="Max DD" value={maxDD ? fmtCompact(maxDD) : '\u2014'} className="text-loss" />
                <MetricCol label="Best Trade" value={biggestWin ? fmtPnlCompact(biggestWin) : '\u2014'} className="text-profit" />
                <MetricCol label="Worst Trade" value={biggestLoss ? fmtPnlCompact(biggestLoss) : '\u2014'} className="text-loss" />
              </div>
            </div>

            {/* Behavior */}
            <div className="rounded border border-border-primary">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-primary">
                <span className="text-[13px] font-semibold text-text-primary">Behavior</span>
                {holdVerdict && <Badge label={holdVerdict} variant={holdVariant} />}
              </div>
              <div className="grid grid-cols-2 divide-x divide-border-secondary">
                <MetricCol label="Avg Win Hold" value={avgWinHold ? fmtHold(avgWinHold) : '\u2014'} className="text-text-primary" />
                <MetricCol label="Avg Loss Hold" value={avgLossHold ? fmtHold(avgLossHold) : '\u2014'} className="text-text-primary" />
              </div>
              <div className="border-t border-border-secondary px-4 py-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase tracking-wider text-text-muted">Streaks</span>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] tabular-nums"><span className="text-profit font-medium">{enriched?.max_consecutive_wins ?? 0}W</span></span>
                    <span className="text-[11px] tabular-nums"><span className="text-loss font-medium">{enriched?.max_consecutive_losses ?? 0}L</span></span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Section 5 — Trade Insights */}
          <div className="rounded border border-border-primary p-4 mt-4">
            <div className="text-[10px] uppercase tracking-wider text-text-muted mb-3">Trade Insights</div>
            {slicePanels.length > 0 ? (
              <div className="grid grid-cols-4 gap-4">
                {slicePanels.map((p) => (
                  <div key={p.title} className="rounded border border-border-secondary p-3">
                    <SlicePanel title={p.title} rows={p.rows} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-text-muted">Trade insights will appear after your first closed trades</div>
            )}
          </div>

          {/* Section 6 — Behavioral Insights */}
          <div className="rounded border border-border-primary p-4 mt-4">
            <div className="text-[10px] uppercase tracking-wider text-text-muted mb-3">Behavioral Insights</div>
            {insights.length > 0 ? (
              <div className="grid grid-cols-3 gap-3">
                {insights.map((insight) => (
                  <div
                    key={insight.label}
                    className={`rounded border px-4 py-3 ${
                      insight.verdict === 'good' ? 'border-profit/30 bg-profit/5' :
                      insight.verdict === 'bad' ? 'border-loss/30 bg-loss/5' :
                      'border-border-secondary'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[12px] font-medium text-text-primary">{insight.label}</span>
                      <Badge
                        label={insight.verdict === 'good' ? 'Good' : insight.verdict === 'bad' ? 'Warning' : 'Neutral'}
                        variant={insight.verdict === 'good' ? 'profit' : insight.verdict === 'bad' ? 'loss' : 'neutral'}
                      />
                    </div>
                    <div className="text-[10px] text-text-muted mb-2">{insight.description}</div>
                    <div className="text-[12px] font-medium tabular-nums text-text-secondary">{insight.value}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-text-muted">Behavioral patterns will be detected as you trade more</div>
            )}
          </div>

          {/* Section 7 — Recent Days */}
          <div className="rounded border border-border-primary p-4 mt-4">
            <div className="text-[10px] uppercase tracking-wider text-text-muted mb-3">Recent Days</div>
            {recentDays.length > 0 ? (
              <HBarChart rows={recentDays} />
            ) : (
              <div className="py-8 text-center text-xs text-text-muted">Daily P&amp;L will appear after your first trading day</div>
            )}
          </div>

          {/* Section 8 — Trade Log */}
          <div className="rounded border border-border-primary mt-4">
            <div className="px-4 py-2.5 border-b border-border-primary">
              <span className="text-[13px] font-semibold text-text-primary">Trade Log</span>
            </div>
            {trades.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="border-b border-border-primary">
                    <tr>
                      <th className="px-4 py-[5px] text-left font-normal text-[10px] uppercase tracking-wider text-text-muted">Strike</th>
                      <th className="px-4 py-[5px] text-left font-normal text-[10px] uppercase tracking-wider text-text-muted w-12"></th>
                      <th className="px-4 py-[5px] text-left font-normal text-[10px] uppercase tracking-wider text-text-muted">Dir</th>
                      <th className="px-4 py-[5px] text-right font-normal text-[10px] uppercase tracking-wider text-text-muted">Lots</th>
                      <th className="px-4 py-[5px] text-right font-normal text-[10px] uppercase tracking-wider text-text-muted">Hold</th>
                      <th className="px-4 py-[5px] text-right font-normal text-[10px] uppercase tracking-wider text-text-muted">DTE</th>
                      <th className="px-4 py-[5px] text-right font-normal text-[10px] uppercase tracking-wider text-text-muted">Spot</th>
                      <th className="px-4 py-[5px] text-right font-normal text-[10px] uppercase tracking-wider text-text-muted">VIX</th>
                      <th className="px-4 py-[5px] text-right font-normal text-[10px] uppercase tracking-wider text-text-muted">P&amp;L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...trades].reverse().map((t, i) => (
                      <tr key={i} className="border-b border-border-secondary/40 hover:bg-bg-hover transition-colors">
                        <td className="px-4 py-1.5 text-text-primary tabular-nums">{t.strike}</td>
                        <td className="px-4 py-1.5">
                          <span className={`text-[9px] px-1.5 py-px rounded-sm font-medium ${
                            t.option_type === 'CE' ? 'bg-signal/10 text-signal' : 'bg-[#ab47bc]/10 text-[#ba68c8]'
                          }`}>{t.option_type}</span>
                        </td>
                        <td className={`px-4 py-1.5 font-medium ${t.direction === 'LONG' ? 'text-profit' : 'text-loss'}`}>{t.direction}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums text-text-primary">{t.lots}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums text-text-secondary">{fmtHold(t.hold_seconds)}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums text-text-secondary">{t.days_to_expiry_at_entry != null ? `${t.days_to_expiry_at_entry}d` : '\u2014'}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums text-text-secondary">{t.spot_at_entry != null ? t.spot_at_entry.toLocaleString('en-IN', { maximumFractionDigits: 0 }) : '\u2014'}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums text-text-secondary">{t.vix_at_entry != null ? t.vix_at_entry.toFixed(1) : '\u2014'}</td>
                        <td className={`px-4 py-1.5 text-right tabular-nums font-medium ${cl(t.realized_pnl)}`}>{fmtPnl(t.realized_pnl)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-text-muted">Your closed trades will appear here</div>
            )}
          </div>

        </LoadingState>
      </div>
    </div>
  )
}
