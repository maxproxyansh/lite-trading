import { useStore } from '../store/useStore'

export default function Analytics() {
  const { analytics } = useStore()

  return (
    <div className="p-4">
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-text-primary">Analytics</h1>
        <p className="text-sm text-text-muted">Portfolio-level execution and equity diagnostics.</p>
      </div>

      <div className="mb-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ['Total Orders', analytics?.total_orders ?? 0],
          ['Filled Orders', analytics?.filled_orders ?? 0],
          ['Win Rate', `${analytics?.win_rate?.toFixed(2) ?? '0.00'}%`],
          ['Equity', analytics?.total_equity?.toLocaleString('en-IN', { maximumFractionDigits: 2 }) ?? '--'],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
            <div className="text-xs uppercase tracking-[0.16em] text-text-muted">{label}</div>
            <div className="mt-3 text-2xl font-semibold text-text-primary">{value}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
          <div className="mb-3 text-sm font-semibold text-text-primary">Equity Curve</div>
          <div className="h-48 overflow-auto rounded-xl bg-bg-primary p-3">
            <pre className="text-[11px] text-text-secondary">{JSON.stringify(analytics?.equity_curve ?? [], null, 2)}</pre>
          </div>
        </section>
        <section className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
          <div className="mb-3 text-sm font-semibold text-text-primary">P&amp;L by Day</div>
          <div className="h-48 overflow-auto rounded-xl bg-bg-primary p-3">
            <pre className="text-[11px] text-text-secondary">{JSON.stringify(analytics?.pnl_by_day ?? [], null, 2)}</pre>
          </div>
        </section>
      </div>
    </div>
  )
}
