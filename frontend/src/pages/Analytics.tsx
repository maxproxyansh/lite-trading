import { useEffect, useRef } from 'react'
import { createChart } from 'lightweight-charts'
import type { IChartApi, Time } from 'lightweight-charts'
import { useShallow } from 'zustand/react/shallow'

import LoadingState from '../components/LoadingState'
import PnLHeatmap from '../components/PnLHeatmap'
import { useStore } from '../store/useStore'

function formatCurrency(value: number): string {
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function EquityCurve({ points }: { points: Array<{ date: string; value: number }> }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current || !points.length) return

    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#1a1a1a' }, textColor: '#666666' },
      grid: { vertLines: { color: '#2e2e2e' }, horzLines: { color: '#2e2e2e' } },
      rightPriceScale: { borderColor: '#363636' },
      timeScale: { borderColor: '#363636' },
      width: containerRef.current.clientWidth,
      height: 220,
    })

    const series = chart.addAreaSeries({
      lineColor: '#387ed1',
      topColor: 'rgba(56, 126, 209, 0.25)',
      bottomColor: 'rgba(56, 126, 209, 0.02)',
      lineWidth: 2,
    })

    series.setData(points.map((p) => ({ time: p.date as Time, value: p.value })))
    chart.timeScale().fitContent()
    chartRef.current = chart

    const observer = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [points])

  if (!points.length) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        Equity curve will appear after your first trade
      </div>
    )
  }

  return <div ref={containerRef} />
}

function PnlTable({ rows }: { rows: Array<{ date: string; pnl: number }> }) {
  if (!rows.length) {
    return <div className="py-8 text-center text-xs text-text-muted">No P&amp;L data yet</div>
  }

  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.pnl)), 1)

  return (
    <div className="space-y-1">
      {rows.map((row) => {
        const positive = row.pnl >= 0
        const pct = Math.abs(row.pnl) / maxAbs * 100
        return (
          <div key={row.date} className="flex items-center gap-3 text-xs">
            <span className="w-20 shrink-0 tabular-nums text-text-muted">{row.date}</span>
            <div className="flex-1">
              <div
                className={`h-4 rounded-sm ${positive ? 'bg-profit/30' : 'bg-loss/30'}`}
                style={{ width: `${Math.max(pct, 2)}%` }}
              />
            </div>
            <span className={`w-20 shrink-0 text-right tabular-nums font-medium ${positive ? 'text-profit' : 'text-loss'}`}>
              {positive ? '+' : ''}{row.pnl.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function Analytics() {
  const { analytics, portfolioLoading } = useStore(useShallow((state) => ({
    analytics: state.analytics,
    portfolioLoading: state.portfolioLoading,
  })))

  const equityCurve: Array<{ date: string; value: number }> = Array.isArray(analytics?.equity_curve)
    ? analytics.equity_curve
        .map((p) => ({
          date: String(p.label ?? '').slice(0, 10),
          value: Number(p.value ?? 0),
        }))
        .filter((p) => /^\d{4}-\d{2}-\d{2}$/.test(p.date))
        .filter((p, i, arr) => i === 0 || p.date !== arr[i - 1].date)
    : []

  const pnlByDay: Array<{ date: string; pnl: number }> = Array.isArray(analytics?.pnl_by_day)
    ? analytics.pnl_by_day.map((p) => ({
        date: String(p.label ?? '').slice(0, 10),
        pnl: Number(p.value ?? 0),
      }))
    : []

  return (
    <div>
      <div className="flex items-center justify-between border-b border-border-primary px-3 h-9">
        <h1 className="text-[12px] font-medium text-text-primary">Analytics</h1>
      </div>

      <div className="p-3">
        <LoadingState loading={portfolioLoading} empty={!analytics} emptyText="No analytics available yet">
          {/* Stat cards */}
          <div className="mb-5 grid grid-cols-4 gap-3">
            {([
              ['Total Orders', analytics?.total_orders ?? 0],
              ['Filled', analytics?.filled_orders ?? 0],
              ['Win Rate', `${(analytics?.win_rate ?? 0).toFixed(1)}%`],
              ['Equity', formatCurrency(analytics?.total_equity ?? 0)],
            ] as const).map(([label, value]) => (
              <div key={label} className="rounded bg-bg-secondary p-3">
                <div className="text-[10px] uppercase tracking-wider text-text-muted">{label}</div>
                <div className="mt-1.5 text-lg font-medium tabular-nums text-text-primary">{value}</div>
              </div>
            ))}
          </div>

          {/* P&L Heatmap */}
          <div className="mb-5">
            <PnLHeatmap data={analytics?.pnl_by_day ?? []} />
          </div>

          {/* Charts */}
          <div className="grid gap-4 xl:grid-cols-2">
            <div className="rounded bg-bg-secondary p-3">
              <div className="mb-2 text-xs font-medium text-text-secondary">Equity Curve</div>
              <EquityCurve points={equityCurve} />
            </div>
            <div className="rounded bg-bg-secondary p-3">
              <div className="mb-2 text-xs font-medium text-text-secondary">P&amp;L by Day</div>
              <div className="max-h-[220px] overflow-auto">
                <PnlTable rows={pnlByDay} />
              </div>
            </div>
          </div>
        </LoadingState>
      </div>
    </div>
  )
}
