import { useEffect, useRef } from 'react'
import { LineChart } from 'lucide-react'

import { useStore } from '../store/useStore'
import type { OptionChainRow } from '../lib/api'

interface Props {
  rows: OptionChainRow[]
  maxOI: number
}

export default function OptionsChainCollapsed({ rows, maxOI }: Props) {
  const { selectedQuote, setSelectedQuote, openOrderModal, addToast } = useStore()
  const atmRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (atmRef.current) {
      atmRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [rows])

  const formatLTP = (ltp: number) => (ltp === 0 ? '--' : ltp.toFixed(2))

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-bg-secondary border-b border-[#222]">
        <div className="grid px-2" style={{ gridTemplateColumns: '1fr 56px 1fr' }}>
          <div className="py-[6px] px-2 text-right text-[9px] font-semibold text-[#555] uppercase tracking-[0.5px]">CE</div>
          <div className="py-[6px] px-2 text-center text-[9px] font-semibold text-[#555] uppercase tracking-[0.5px]">Strike</div>
          <div className="py-[6px] px-2 text-left text-[9px] font-semibold text-[#555] uppercase tracking-[0.5px]">PE</div>
        </div>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto">
        {rows.map((row) => {
          const isATM = row.is_atm
          const activeCall = selectedQuote?.symbol === row.call.symbol
          const activePut = selectedQuote?.symbol === row.put.symbol

          const callOI = (row.call as Record<string, unknown>).oi_lakhs as number | null
          const putOI = (row.put as Record<string, unknown>).oi_lakhs as number | null

          const callOIWidth = callOI != null ? Math.min((callOI / maxOI) * 100, 100) : 0
          const putOIWidth = putOI != null ? Math.min((putOI / maxOI) * 100, 100) : 0

          const oiOpacity = isATM ? 0.35 : 0.25

          return (
            <div
              key={row.strike}
              ref={isATM ? atmRef : undefined}
            >
              {/* Data row */}
              <div
                className={`group grid border-b border-[#222] px-2 transition-colors ${
                  isATM
                    ? 'bg-[rgba(229,83,75,0.05)] border-l-2 border-l-[rgba(229,83,75,0.4)]'
                    : 'hover:bg-bg-hover'
                }`}
                style={{ gridTemplateColumns: '1fr 56px 1fr', height: '26px' }}
              >
                {/* CE LTP + B/S */}
                <div
                  className={`group/ce relative cursor-pointer flex items-center justify-end px-1 ${
                    activeCall ? 'bg-profit/15' : ''
                  }`}
                  onClick={() => setSelectedQuote(row.call)}
                >
                  <span
                    className={`tabular-nums text-[11px] group-hover/ce:opacity-40 ${
                      isATM ? 'text-[#e0e0e0] font-medium' : 'text-[#b0b0b0]'
                    }`}
                    style={{ fontVariantNumeric: 'tabular-nums' }}
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

                {/* Strike + chart button */}
                <div className="flex items-center justify-center gap-0.5 px-1">
                  <button
                    onClick={() => addToast('info', `Option charts coming soon — ${row.strike} CE/PE`)}
                    className="hidden group-hover:inline-flex h-[16px] w-[16px] items-center justify-center text-text-muted hover:text-text-primary"
                    title="View option chart"
                  >
                    <LineChart size={10} />
                  </button>
                  <span
                    className={`text-[10px] font-medium tabular-nums ${
                      isATM ? 'text-[#e53935] font-bold' : 'text-[#666]'
                    }`}
                    style={{ fontVariantNumeric: 'tabular-nums' }}
                  >
                    {row.strike}
                  </span>
                </div>

                {/* PE LTP + B/S */}
                <div
                  className={`group/pe relative cursor-pointer flex items-center justify-start px-1 ${
                    activePut ? 'bg-loss/15' : ''
                  }`}
                  onClick={() => setSelectedQuote(row.put)}
                >
                  <span
                    className={`tabular-nums text-[11px] group-hover/pe:opacity-40 ${
                      isATM ? 'text-[#e0e0e0] font-medium' : 'text-[#b0b0b0]'
                    }`}
                    style={{ fontVariantNumeric: 'tabular-nums' }}
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
              </div>

              {/* OI bar row */}
              <div
                className="grid mb-[1px]"
                style={{ gridTemplateColumns: '1fr 56px 1fr', height: '3px' }}
              >
                {/* CE bar: grows from right */}
                <div className="relative overflow-hidden">
                  <div
                    className="absolute right-0 top-0 h-full"
                    style={{
                      width: `${callOIWidth}%`,
                      backgroundColor: `rgba(229,83,75,${oiOpacity})`,
                    }}
                  />
                </div>
                {/* Strike column spacer */}
                <div />
                {/* PE bar: grows from left */}
                <div className="relative overflow-hidden">
                  <div
                    className="absolute left-0 top-0 h-full"
                    style={{
                      width: `${putOIWidth}%`,
                      backgroundColor: `rgba(76,175,80,${oiOpacity})`,
                    }}
                  />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
