type Props = {
  rows: Array<{ label: string; value: number }>
  maxRows?: number
}

function fmtValue(v: number): string {
  const sign = v >= 0 ? '+' : '-'
  return `${sign}\u20B9${Math.abs(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export default function HBarChart({ rows, maxRows }: Props) {
  const visible = maxRows ? rows.slice(0, maxRows) : rows
  const maxAbs = Math.max(...visible.map((r) => Math.abs(r.value)), 1)

  return (
    <div className="space-y-px">
      {visible.map((row) => {
        const pct = Math.max((Math.abs(row.value) / maxAbs) * 100, 3)
        const isProfit = row.value >= 0
        return (
          <div key={row.label} className="flex items-center gap-2 py-[3px]">
            <span className="w-[66px] shrink-0 text-[10px] text-text-muted tabular-nums">
              {row.label}
            </span>
            <div className="flex-1 h-[14px] relative">
              <div
                className={`h-full rounded-[2px] ${isProfit ? 'bg-profit/20' : 'bg-loss/20'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span
              className={`w-[76px] shrink-0 text-right text-[10px] font-medium tabular-nums ${
                isProfit ? 'text-profit' : 'text-loss'
              }`}
            >
              {fmtValue(row.value)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
