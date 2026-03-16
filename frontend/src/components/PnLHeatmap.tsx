import { useMemo, useState } from 'react'

interface HeatmapProps {
  data: { label: string; value: number }[]
  monthsToShow?: number
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const GAP = 4
const CELL = 20

const PROFIT_COLORS = [
  'rgba(76,175,80,0.2)',
  'rgba(76,175,80,0.4)',
  'rgba(76,175,80,0.65)',
  'rgba(76,175,80,0.9)',
]
const LOSS_COLORS = [
  'rgba(229,57,53,0.2)',
  'rgba(229,57,53,0.4)',
  'rgba(229,57,53,0.65)',
  'rgba(229,57,53,0.9)',
]
const EMPTY_COLOR = '#2a2a2a'

function getColor(value: number, profitTh: number[], lossTh: number[]): string {
  if (value === 0) return EMPTY_COLOR
  if (value > 0) {
    if (value <= profitTh[0]) return PROFIT_COLORS[0]
    if (value <= profitTh[1]) return PROFIT_COLORS[1]
    if (value <= profitTh[2]) return PROFIT_COLORS[2]
    return PROFIT_COLORS[3]
  }
  const abs = Math.abs(value)
  if (abs <= lossTh[0]) return LOSS_COLORS[0]
  if (abs <= lossTh[1]) return LOSS_COLORS[1]
  if (abs <= lossTh[2]) return LOSS_COLORS[2]
  return LOSS_COLORS[3]
}

function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0
  const pos = (sorted.length - 1) * q
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  if (lo === hi) return sorted[lo]
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo)
}

type MonthBlock = {
  label: string
  cells: Array<{ date: string; value: number; week: number; dow: number; isFuture: boolean }>
  totalWeeks: number
}

export default function PnLHeatmap({ data, monthsToShow = 12 }: HeatmapProps) {
  const [selected, setSelected] = useState<{ date: string; value: number } | null>(null)

  const { months, profitTh, lossTh } = useMemo(() => {
    const pnlMap = new Map<string, number>()
    for (const d of data) {
      const ds = String(d.label ?? '').slice(0, 10)
      if (/^\d{4}-\d{2}-\d{2}$/.test(ds)) pnlMap.set(ds, d.value)
    }

    const profits = data.filter((d) => d.value > 0).map((d) => d.value).sort((a, b) => a - b)
    const losses = data.filter((d) => d.value < 0).map((d) => Math.abs(d.value)).sort((a, b) => a - b)
    const pTh = [quantile(profits, 0.25), quantile(profits, 0.5), quantile(profits, 0.75)]
    const lTh = [quantile(losses, 0.25), quantile(losses, 0.5), quantile(losses, 0.75)]

    const today = new Date()
    const start = new Date(today)
    start.setMonth(start.getMonth() - (monthsToShow - 1))
    start.setDate(1)

    const monthBlocks: MonthBlock[] = []
    const cursor = new Date(start)

    while (cursor.getFullYear() < today.getFullYear() || (cursor.getFullYear() === today.getFullYear() && cursor.getMonth() <= today.getMonth())) {
      const year = cursor.getFullYear()
      const month = cursor.getMonth()
      const firstDay = new Date(year, month, 1)
      const daysInMonth = new Date(year, month + 1, 0).getDate()

      const cells: MonthBlock['cells'] = []
      let maxWeek = 0

      for (let day = 1; day <= daysInMonth; day++) {
        const d = new Date(year, month, day)
        const iso = d.toISOString().slice(0, 10)
        const rawDow = d.getDay()
        const dow = rawDow === 0 ? 6 : rawDow - 1
        const firstDow = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1
        const week = Math.floor((day - 1 + firstDow) / 7)
        if (week > maxWeek) maxWeek = week

        cells.push({ date: iso, value: pnlMap.get(iso) ?? 0, week, dow, isFuture: d > today })
      }

      const shortMonth = MONTHS[month].slice(0, 3)
      const label = month === 0 ? `${shortMonth} ${year}` : shortMonth

      monthBlocks.push({ label, cells, totalWeeks: maxWeek + 1 })

      cursor.setMonth(cursor.getMonth() + 1)
      cursor.setDate(1)
    }

    return { months: monthBlocks, profitTh: pTh, lossTh: lTh }
  }, [data, monthsToShow])

  const blockH = 7 * (CELL + GAP) - GAP

  return (
    <div>
      {/* Scrollable month blocks */}
      <div className="overflow-x-auto heatmap-scroll" style={{ scrollbarWidth: 'none' }}>
        <style>{`.heatmap-scroll::-webkit-scrollbar { display: none; }`}</style>
        <div className="inline-flex gap-10 py-2 px-1" style={{ minWidth: 'max-content' }}>
          {months.map((m) => {
            const blockW = m.totalWeeks * (CELL + GAP) - GAP
            return (
              <div key={m.label}>
                <div className="text-[11px] text-text-secondary mb-3 font-medium">{m.label}</div>
                <div className="relative" style={{ width: blockW, height: blockH }}>
                  {m.cells.map((cell) =>
                    cell.isFuture ? null : (
                      <div
                        key={cell.date}
                        className={`absolute rounded-[2px] cursor-pointer transition-opacity duration-75 ${
                          selected && selected.date !== cell.date ? 'opacity-25' : ''
                        }`}
                        style={{
                          width: CELL,
                          height: CELL,
                          left: cell.week * (CELL + GAP),
                          top: cell.dow * (CELL + GAP),
                          backgroundColor: getColor(cell.value, profitTh, lossTh),
                          outline: selected?.date === cell.date ? '2px solid #e0e0e0' : 'none',
                          outlineOffset: 1,
                        }}
                        onClick={() => setSelected((prev) => prev?.date === cell.date ? null : { date: cell.date, value: cell.value })}
                      />
                    ),
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Selected day detail */}
      {selected && (
        <div className="text-center mt-3">
          <span className="text-[12px] text-text-secondary">
            Gross realised P&L on{' '}
            <span className="font-medium text-text-primary">{selected.date}</span>
            {' : '}
            <span className={`font-semibold ${selected.value >= 0 ? 'text-profit' : 'text-loss'}`}>
              {selected.value >= 0 ? '+' : ''}₹{Math.abs(selected.value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
            </span>
          </span>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center justify-center gap-1.5 mt-3 text-[9px] text-text-muted">
        <span>Loss</span>
        {[...LOSS_COLORS].reverse().map((c, i) => (
          <div key={`l${i}`} className="rounded-[2px]" style={{ width: 10, height: 10, backgroundColor: c }} />
        ))}
        <div className="rounded-[2px]" style={{ width: 10, height: 10, backgroundColor: EMPTY_COLOR }} />
        {PROFIT_COLORS.map((c, i) => (
          <div key={`p${i}`} className="rounded-[2px]" style={{ width: 10, height: 10, backgroundColor: c }} />
        ))}
        <span>Profit</span>
      </div>
    </div>
  )
}
