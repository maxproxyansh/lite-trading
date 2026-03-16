import type { SliceRow } from './types'

type Props = {
  title: string
  rows: SliceRow[]
}

function fmtPnl(v: number): string {
  const sign = v >= 0 ? '+' : '-'
  return `${sign}\u20B9${Math.abs(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export default function SlicePanel({ title, rows }: Props) {
  if (!rows.length) return null

  return (
    <div>
      <div className="text-[11px] font-medium text-text-secondary mb-2">{title}</div>
      <div>
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between py-1.5 border-b border-[#222] last:border-0"
          >
            <div className="flex items-baseline">
              <span className="text-[11px] text-text-primary">{row.label}</span>
              <span className="text-[10px] text-text-muted ml-1.5">{row.count}</span>
            </div>
            <div className="flex items-baseline">
              <span className="text-[10px] text-text-muted">{row.winRate}%</span>
              <span
                className={`text-[11px] font-medium tabular-nums ml-2 ${
                  row.totalPnl >= 0 ? 'text-profit' : 'text-loss'
                }`}
              >
                {fmtPnl(row.totalPnl)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
