import { memo, useEffect, useRef, type Ref } from 'react'
import { LineChart } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'

import type { OptionChainRow, OptionQuote } from '../lib/api'
import { useStore } from '../store/useStore'

interface Props {
  rows: OptionChainRow[]
  maxOI: number
  activeExpiry: string | null
}

function formatLTP(ltp: number) {
  return ltp === 0 ? '--' : ltp.toFixed(2)
}

const OptionsChainCollapsedRow = memo(function OptionsChainCollapsedRow({
  row,
  maxOI,
  selectedQuoteSymbol,
  activeChartSymbol,
  onSelectQuote,
  onOrder,
  onViewChart,
  rowRef,
}: {
  row: OptionChainRow
  maxOI: number
  selectedQuoteSymbol: string | null
  activeChartSymbol: string | null
  onSelectQuote: (quote: OptionQuote) => void
  onOrder: (quote: OptionQuote, side: 'BUY' | 'SELL') => void
  onViewChart: (quote: OptionQuote) => void
  rowRef?: Ref<HTMLDivElement>
}) {
  const isATM = row.is_atm
  const activeCall = selectedQuoteSymbol === row.call.symbol
  const activePut = selectedQuoteSymbol === row.put.symbol
  const chartingCall = activeChartSymbol === row.call.symbol
  const chartingPut = activeChartSymbol === row.put.symbol
  const callOI = (row.call as Record<string, unknown>).oi_lakhs as number | null
  const putOI = (row.put as Record<string, unknown>).oi_lakhs as number | null
  const callOIWidth = callOI != null ? Math.min((callOI / maxOI) * 100, 100) : 0
  const putOIWidth = putOI != null ? Math.min((putOI / maxOI) * 100, 100) : 0
  const oiOpacity = isATM ? 0.35 : 0.25

  return (
    <div ref={rowRef}>
      <div
        className={`group grid border-b border-[#222] px-2 transition-colors ${
          isATM
            ? 'border-l-2 border-l-[rgba(229,83,75,0.4)] bg-[rgba(229,83,75,0.05)]'
            : 'hover:bg-bg-hover'
        }`}
        style={{ gridTemplateColumns: '1fr 56px 1fr', height: '24px' }}
      >
        <div
          className={`group/ce relative flex cursor-pointer items-center justify-end px-1 ${
            activeCall ? 'bg-profit/15' : ''
          }`}
          onClick={() => onSelectQuote(row.call)}
        >
          <span
            className={`tabular-nums text-[11px] group-hover/ce:opacity-40 ${
              isATM ? 'font-medium text-[#e0e0e0]' : 'text-[#b0b0b0]'
            }`}
            style={{ fontVariantNumeric: 'tabular-nums' }}
          >
            {formatLTP(row.call.ltp)}
          </span>
          <div className="absolute inset-0 hidden items-center justify-center gap-0.5 group-hover/ce:flex">
            <button
              onClick={(event) => {
                event.stopPropagation()
                onViewChart(row.call)
              }}
              className={`flex h-[18px] w-[18px] items-center justify-center rounded-sm text-white ${
                chartingCall ? 'bg-brand text-bg-primary' : 'bg-[#2b2b2b] text-[#d0d0d0]'
              }`}
              title="View CE chart"
            >
              <LineChart size={10} />
            </button>
            <button
              onClick={(event) => {
                event.stopPropagation()
                onOrder(row.call, 'BUY')
              }}
              className="h-[18px] w-[18px] rounded-sm bg-btn-buy text-[9px] font-bold text-white"
            >
              B
            </button>
            <button
              onClick={(event) => {
                event.stopPropagation()
                onOrder(row.call, 'SELL')
              }}
              className="h-[18px] w-[18px] rounded-sm bg-btn-sell text-[9px] font-bold text-white"
            >
              S
            </button>
          </div>
        </div>

        <div className="flex items-center justify-center gap-0.5 px-1">
          <span
            className={`text-[10px] tabular-nums ${
              isATM ? 'font-bold text-[#e53935]' : 'font-medium text-[#666]'
            }`}
            style={{ fontVariantNumeric: 'tabular-nums' }}
          >
            {row.strike}
          </span>
        </div>

        <div
          className={`group/pe relative flex cursor-pointer items-center justify-start px-1 ${
            activePut ? 'bg-loss/15' : ''
          }`}
          onClick={() => onSelectQuote(row.put)}
        >
          <span
            className={`tabular-nums text-[11px] group-hover/pe:opacity-40 ${
              isATM ? 'font-medium text-[#e0e0e0]' : 'text-[#b0b0b0]'
            }`}
            style={{ fontVariantNumeric: 'tabular-nums' }}
          >
            {formatLTP(row.put.ltp)}
          </span>
          <div className="absolute inset-0 hidden items-center justify-center gap-0.5 group-hover/pe:flex">
            <button
              onClick={(event) => {
                event.stopPropagation()
                onViewChart(row.put)
              }}
              className={`flex h-[18px] w-[18px] items-center justify-center rounded-sm text-white ${
                chartingPut ? 'bg-brand text-bg-primary' : 'bg-[#2b2b2b] text-[#d0d0d0]'
              }`}
              title="View PE chart"
            >
              <LineChart size={10} />
            </button>
            <button
              onClick={(event) => {
                event.stopPropagation()
                onOrder(row.put, 'BUY')
              }}
              className="h-[18px] w-[18px] rounded-sm bg-btn-buy text-[9px] font-bold text-white"
            >
              B
            </button>
            <button
              onClick={(event) => {
                event.stopPropagation()
                onOrder(row.put, 'SELL')
              }}
              className="h-[18px] w-[18px] rounded-sm bg-btn-sell text-[9px] font-bold text-white"
            >
              S
            </button>
          </div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 56px 1fr', height: '2px' }}>
        <div className="relative overflow-hidden">
          <div
            className="absolute right-0 top-0 h-full"
            style={{
              width: `${callOIWidth}%`,
              backgroundColor: `rgba(229,83,75,${oiOpacity})`,
            }}
          />
        </div>
        <div />
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
})

export default function OptionsChainCollapsed({ rows, maxOI, activeExpiry }: Props) {
  const { selectedQuoteSymbol, optionChartSymbol, setSelectedQuote, setOptionChartSymbol, openOrderModal } = useStore(useShallow((state) => ({
    selectedQuoteSymbol: state.selectedQuote?.symbol ?? null,
    optionChartSymbol: state.optionChartSymbol,
    setSelectedQuote: state.setSelectedQuote,
    setOptionChartSymbol: state.setOptionChartSymbol,
    openOrderModal: state.openOrderModal,
  })))
  const atmRef = useRef<HTMLDivElement>(null)
  const scrolledExpiryRef = useRef<string | null>(null)

  useEffect(() => {
    if (!atmRef.current || !activeExpiry || scrolledExpiryRef.current === activeExpiry) {
      return
    }
    atmRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' })
    scrolledExpiryRef.current = activeExpiry
  }, [activeExpiry, rows])

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="sticky top-0 z-10 border-b border-[#222] bg-bg-secondary">
        <div className="grid px-2" style={{ gridTemplateColumns: '1fr 56px 1fr' }}>
          <div className="px-2 py-[6px] text-right text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">CE</div>
          <div className="px-2 py-[6px] text-center text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">Strike</div>
          <div className="px-2 py-[6px] text-left text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">PE</div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {rows.map((row) => (
          <OptionsChainCollapsedRow
            key={row.strike}
            row={row}
            maxOI={maxOI}
            selectedQuoteSymbol={selectedQuoteSymbol}
            activeChartSymbol={optionChartSymbol}
            onSelectQuote={setSelectedQuote}
            onViewChart={(quote) => {
              setSelectedQuote(quote)
              setOptionChartSymbol(optionChartSymbol === quote.symbol ? null : quote.symbol)
            }}
            onOrder={openOrderModal}
            rowRef={row.is_atm ? atmRef : undefined}
          />
        ))}
      </div>
    </div>
  )
}
