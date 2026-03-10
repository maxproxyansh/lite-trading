import { useMemo, useState } from 'react'

interface HeatmapProps {
  data: { label: string; value: number }[]
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DAY_LABELS = ['Mon', '', 'Wed', '', 'Fri', '', '']

const CELL_SIZE = 12
const GAP = 2

const PROFIT_COLORS = [
  'rgba(76, 175, 80, 0.2)',
  'rgba(76, 175, 80, 0.4)',
  'rgba(76, 175, 80, 0.7)',
  'rgba(76, 175, 80, 1)',
]
const LOSS_COLORS = [
  'rgba(229, 57, 53, 0.2)',
  'rgba(229, 57, 53, 0.4)',
  'rgba(229, 57, 53, 0.7)',
  'rgba(229, 57, 53, 1)',
]
const EMPTY_COLOR = '#2a2a2a'

function getColor(value: number, profitThresholds: number[], lossThresholds: number[]): string {
  if (value === 0) return EMPTY_COLOR
  if (value > 0) {
    if (value <= profitThresholds[0]) return PROFIT_COLORS[0]
    if (value <= profitThresholds[1]) return PROFIT_COLORS[1]
    if (value <= profitThresholds[2]) return PROFIT_COLORS[2]
    return PROFIT_COLORS[3]
  }
  const abs = Math.abs(value)
  if (abs <= lossThresholds[0]) return LOSS_COLORS[0]
  if (abs <= lossThresholds[1]) return LOSS_COLORS[1]
  if (abs <= lossThresholds[2]) return LOSS_COLORS[2]
  return LOSS_COLORS[3]
}

function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return 0
  const pos = (sorted.length - 1) * q
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  if (lo === hi) return sorted[lo]
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo)
}

export default function PnLHeatmap({ data }: HeatmapProps) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; date: string; value: number } | null>(null)

  const { cells, weeks, monthLabels, profitThresholds, lossThresholds } = useMemo(() => {
    // Build date -> pnl map
    const pnlMap = new Map<string, number>()
    for (const d of data) {
      const dateStr = String(d.label ?? '').slice(0, 10)
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        pnlMap.set(dateStr, d.value)
      }
    }

    // Compute quantile thresholds
    const profits = data.filter((d) => d.value > 0).map((d) => d.value).sort((a, b) => a - b)
    const losses = data.filter((d) => d.value < 0).map((d) => Math.abs(d.value)).sort((a, b) => a - b)

    const profitTh = [quantile(profits, 0.25), quantile(profits, 0.5), quantile(profits, 0.75)]
    const lossTh = [quantile(losses, 0.25), quantile(losses, 0.5), quantile(losses, 0.75)]

    // Generate grid for last ~5 months
    const today = new Date()
    const startDate = new Date(today)
    startDate.setMonth(startDate.getMonth() - 5)
    // Align to Monday
    const dayOfWeek = startDate.getDay()
    const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek
    startDate.setDate(startDate.getDate() + mondayOffset)

    const cellList: Array<{ date: string; value: number; col: number; row: number; isFuture: boolean }> = []
    const weekList: number[] = []
    const monthLabelList: Array<{ label: string; col: number }> = []

    let col = 0
    let lastMonth = -1
    const cursor = new Date(startDate)

    while (cursor <= today || cursor.getDay() !== 1) {
      if (cursor > today && cursor.getDay() === 1) break

      const isoDate = cursor.toISOString().slice(0, 10)
      // row: 0=Mon, 1=Tue, ..., 6=Sun
      const dow = cursor.getDay()
      const row = dow === 0 ? 6 : dow - 1

      if (row === 0) {
        weekList.push(col)
        const m = cursor.getMonth()
        if (m !== lastMonth) {
          monthLabelList.push({ label: MONTHS[m], col })
          lastMonth = m
        }
      }

      const isFuture = cursor > today
      const pnl = pnlMap.get(isoDate) ?? 0

      cellList.push({ date: isoDate, value: pnl, col, row, isFuture })

      cursor.setDate(cursor.getDate() + 1)
      if (row === 6) col++
    }

    return { cells: cellList, weeks: weekList, monthLabels: monthLabelList, profitThresholds: profitTh, lossThresholds: lossTh }
  }, [data])

  const totalCols = weeks.length
  const gridWidth = totalCols * (CELL_SIZE + GAP)

  return (
    <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
      <h3 className="text-sm font-medium text-text-primary mb-3">P&L Heatmap</h3>
      <div className="overflow-x-auto">
        <div className="inline-flex gap-2">
          {/* Day labels */}
          <div className="flex flex-col shrink-0" style={{ gap: GAP, paddingTop: 18 }}>
            {DAY_LABELS.map((label, i) => (
              <div
                key={i}
                className="text-text-muted"
                style={{ height: CELL_SIZE, fontSize: 9, lineHeight: `${CELL_SIZE}px` }}
              >
                {label}
              </div>
            ))}
          </div>

          {/* Grid area */}
          <div>
            {/* Month labels */}
            <div className="relative" style={{ height: 14, width: gridWidth, marginBottom: 4 }}>
              {monthLabels.map((m) => (
                <span
                  key={`${m.label}-${m.col}`}
                  className="absolute text-text-muted"
                  style={{ left: m.col * (CELL_SIZE + GAP), fontSize: 9, top: 0 }}
                >
                  {m.label}
                </span>
              ))}
            </div>

            {/* Cells grid */}
            <div
              className="relative"
              style={{ width: gridWidth, height: 7 * (CELL_SIZE + GAP) - GAP }}
              onMouseLeave={() => setTooltip(null)}
            >
              {cells.map((cell) =>
                cell.isFuture ? null : (
                  <div
                    key={cell.date}
                    className="absolute rounded-sm"
                    style={{
                      width: CELL_SIZE,
                      height: CELL_SIZE,
                      left: cell.col * (CELL_SIZE + GAP),
                      top: cell.row * (CELL_SIZE + GAP),
                      backgroundColor: getColor(cell.value, profitThresholds, lossThresholds),
                    }}
                    onMouseEnter={(e) => {
                      const rect = (e.target as HTMLElement).getBoundingClientRect()
                      const parent = (e.target as HTMLElement).closest('.overflow-x-auto')?.getBoundingClientRect()
                      if (parent) {
                        setTooltip({
                          x: rect.left - parent.left + CELL_SIZE / 2,
                          y: rect.top - parent.top - 4,
                          date: cell.date,
                          value: cell.value,
                        })
                      }
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  />
                ),
              )}

              {/* Tooltip */}
              {tooltip && (
                <div
                  className="absolute z-10 rounded-sm bg-bg-primary border border-border-primary px-2 py-1 text-xs text-text-primary pointer-events-none whitespace-nowrap"
                  style={{
                    left: tooltip.x,
                    top: tooltip.y,
                    transform: 'translate(-50%, -100%)',
                  }}
                >
                  <span className="text-text-muted">{tooltip.date}</span>
                  {' '}
                  <span className={tooltip.value >= 0 ? 'text-profit' : 'text-loss'}>
                    {tooltip.value >= 0 ? '+' : ''}
                    {tooltip.value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-end gap-1.5 mt-3 text-text-muted" style={{ fontSize: 9 }}>
          <span>Loss</span>
          {[...LOSS_COLORS].reverse().map((c, i) => (
            <div key={`l${i}`} className="rounded-sm" style={{ width: 10, height: 10, backgroundColor: c }} />
          ))}
          <div className="rounded-sm" style={{ width: 10, height: 10, backgroundColor: EMPTY_COLOR }} />
          {PROFIT_COLORS.map((c, i) => (
            <div key={`p${i}`} className="rounded-sm" style={{ width: 10, height: 10, backgroundColor: c }} />
          ))}
          <span>Profit</span>
        </div>
      </div>
    </div>
  )
}
