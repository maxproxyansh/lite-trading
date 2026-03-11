import { useEffect, useRef } from 'react'
import { LineChart } from 'lucide-react'

import { useStore } from '../store/useStore'
import type { OptionChainRow } from '../lib/api'

interface Props {
  rows: OptionChainRow[]
  maxOI: number
}

export default function OptionsChainExpanded({ rows, maxOI }: Props) {
  const { selectedQuote, setSelectedQuote, openOrderModal, addToast } = useStore()
  const atmRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (atmRef.current) {
      atmRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [rows])

  const formatLTP = (ltp: number) => (ltp === 0 ? '--' : ltp.toFixed(2))
  const formatOI = (oi: number | null) => (oi == null ? '--' : Math.round(oi) + 'L')

  return (
    <div className="flex-1 overflow-auto">
      {/* Header */}
      <div
        className="sticky top-0 z-10 bg-bg-secondary grid items-center border-b border-[#2a2a2a]"
        style={{ gridTemplateColumns: '44px 38px 1fr 50px 1fr 38px 44px' }}
      >
        <div className="text-[8px] font-semibold text-[#555] uppercase tracking-[0.4px] text-center py-[4px]">OI</div>
        <div className="text-[8px] font-semibold text-[#555] uppercase tracking-[0.4px] text-center py-[4px]">IV</div>
        <div className="text-[8px] font-semibold text-[#555] uppercase tracking-[0.4px] text-right pr-1 py-[4px]">CE</div>
        <div className="text-[8px] font-semibold text-[#555] uppercase tracking-[0.4px] text-center py-[4px]">Strike</div>
        <div className="text-[8px] font-semibold text-[#555] uppercase tracking-[0.4px] text-left pl-1 py-[4px]">PE</div>
        <div className="text-[8px] font-semibold text-[#555] uppercase tracking-[0.4px] text-center py-[4px]">IV</div>
        <div className="text-[8px] font-semibold text-[#555] uppercase tracking-[0.4px] text-center py-[4px]">OI</div>
      </div>

      {/* Rows */}
      {rows.map((row) => {
        const isATM = row.is_atm
        const activeCall = selectedQuote?.symbol === row.call.symbol
        const activePut = selectedQuote?.symbol === row.put.symbol
        const callOI = (row.call as Record<string, unknown>).oi_lakhs as number | null ?? null
        const putOI = (row.put as Record<string, unknown>).oi_lakhs as number | null ?? null
        const callOIPct = Math.min(100, callOI != null && maxOI > 0 ? (callOI / maxOI) * 100 : 0)
        const putOIPct = Math.min(100, putOI != null && maxOI > 0 ? (putOI / maxOI) * 100 : 0)
        const rowH = isATM ? 28 : 26
        const oiBgOpacity = isATM ? 0.20 : 0.15

        return (
          <div
            key={row.strike}
            ref={isATM ? atmRef : undefined}
            className={`group grid border-b border-[#222] transition-colors ${
              isATM
                ? 'bg-[rgba(229,83,75,0.05)] border-l-2 border-l-[rgba(229,83,75,0.4)]'
                : 'hover:bg-bg-hover'
            }`}
            style={{
              gridTemplateColumns: '44px 38px 1fr 50px 1fr 38px 44px',
              height: rowH,
            }}
          >
            {/* CE OI — bar fills right-to-left */}
            <div
              className="relative overflow-hidden flex items-center justify-end"
              style={{ borderRadius: 1 }}
            >
              <div
                className="absolute inset-y-0 right-0"
                style={{
                  width: `${callOIPct}%`,
                  background: `rgba(229,83,75,${oiBgOpacity})`,
                }}
              />
              <span className="relative z-10 text-[9px] text-[#555] tabular-nums pr-[3px]">
                {formatOI(callOI)}
              </span>
            </div>

            {/* CE IV */}
            <div className="flex items-center justify-center text-[9px] text-[#555] tabular-nums">
              {row.call.iv != null ? row.call.iv.toFixed(1) : '--'}
            </div>

            {/* CE LTP + B/S */}
            <div
              className={`group/ce relative cursor-pointer flex items-center justify-end pr-1 ${
                activeCall ? 'bg-profit/15' : ''
              }`}
              onClick={() => setSelectedQuote(row.call)}
            >
              <span
                className={`tabular-nums group-hover/ce:opacity-40 ${
                  isATM
                    ? 'text-[11px] text-[#e0e0e0] font-semibold'
                    : 'text-[11px] text-[#b0b0b0]'
                }`}
              >
                {formatLTP(row.call.ltp)}
              </span>
              <div className="absolute inset-0 hidden group-hover/ce:flex items-center justify-center gap-0.5">
                <button
                  onClick={(e) => { e.stopPropagation(); openOrderModal(row.call, 'BUY') }}
                  className="h-[18px] w-[18px] rounded-sm bg-btn-buy text-[9px] font-bold text-white"
                >B</button>
                <button
                  onClick={(e) => { e.stopPropagation(); openOrderModal(row.call, 'SELL') }}
                  className="h-[18px] w-[18px] rounded-sm bg-btn-sell text-[9px] font-bold text-white"
                >S</button>
              </div>
            </div>

            {/* Strike + chart icon */}
            <div
              className={`flex items-center justify-center tabular-nums ${
                isATM
                  ? 'text-[10px] font-bold text-[#e53935] bg-[rgba(229,83,75,0.08)]'
                  : 'text-[10px] font-semibold text-[#666] bg-[#232323]'
              }`}
            >
              <button
                onClick={() => addToast('info', `Option charts coming soon — ${row.strike} CE/PE`)}
                className="hidden group-hover:inline-flex h-[16px] w-[16px] items-center justify-center text-[#555] hover:text-[#aaa] mr-[2px]"
                title="View option chart"
              >
                <LineChart size={10} />
              </button>
              <span>{row.strike}</span>
            </div>

            {/* PE LTP + B/S */}
            <div
              className={`group/pe relative cursor-pointer flex items-center justify-start pl-1 ${
                activePut ? 'bg-loss/15' : ''
              }`}
              onClick={() => setSelectedQuote(row.put)}
            >
              <span
                className={`tabular-nums group-hover/pe:opacity-40 ${
                  isATM
                    ? 'text-[11px] text-[#e0e0e0] font-semibold'
                    : 'text-[11px] text-[#b0b0b0]'
                }`}
              >
                {formatLTP(row.put.ltp)}
              </span>
              <div className="absolute inset-0 hidden group-hover/pe:flex items-center justify-center gap-0.5">
                <button
                  onClick={(e) => { e.stopPropagation(); openOrderModal(row.put, 'BUY') }}
                  className="h-[18px] w-[18px] rounded-sm bg-btn-buy text-[9px] font-bold text-white"
                >B</button>
                <button
                  onClick={(e) => { e.stopPropagation(); openOrderModal(row.put, 'SELL') }}
                  className="h-[18px] w-[18px] rounded-sm bg-btn-sell text-[9px] font-bold text-white"
                >S</button>
              </div>
            </div>

            {/* PE IV */}
            <div className="flex items-center justify-center text-[9px] text-[#555] tabular-nums">
              {row.put.iv != null ? row.put.iv.toFixed(1) : '--'}
            </div>

            {/* PE OI — bar fills left-to-right */}
            <div
              className="relative overflow-hidden flex items-center justify-start"
              style={{ borderRadius: 1 }}
            >
              <div
                className="absolute inset-y-0 left-0"
                style={{
                  width: `${putOIPct}%`,
                  background: `rgba(76,175,80,${oiBgOpacity})`,
                }}
              />
              <span className="relative z-10 text-[9px] text-[#555] tabular-nums pl-[3px]">
                {formatOI(putOI)}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
