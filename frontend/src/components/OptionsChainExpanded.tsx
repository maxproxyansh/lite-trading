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

function formatOI(oi: number | null) {
  return oi == null ? '--' : `${Math.round(oi)}L`
}

const OptionsChainExpandedRow = memo(function OptionsChainExpandedRow({
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
  const callOI = (row.call as Record<string, unknown>).oi_lakhs as number | null ?? null
  const putOI = (row.put as Record<string, unknown>).oi_lakhs as number | null ?? null
  const callOIPct = Math.min(100, callOI != null && maxOI > 0 ? (callOI / maxOI) * 100 : 0)
  const putOIPct = Math.min(100, putOI != null && maxOI > 0 ? (putOI / maxOI) * 100 : 0)
  const rowHeight = isATM ? 28 : 26
  const oiBgOpacity = isATM ? 0.2 : 0.15

  return (
    <div
      ref={rowRef}
      className={`group grid border-b border-[#222] transition-colors ${
        isATM
          ? 'border-l-2 border-l-[rgba(229,83,75,0.4)] bg-[rgba(229,83,75,0.05)]'
          : 'hover:bg-bg-hover'
      }`}
      style={{ gridTemplateColumns: '44px 38px 1fr 50px 1fr 38px 44px', height: rowHeight }}
    >
      <div className="relative flex items-center justify-end overflow-hidden" style={{ borderRadius: 1 }}>
        <div
          className="absolute inset-y-0 right-0"
          style={{
            width: `${callOIPct}%`,
            background: `rgba(229,83,75,${oiBgOpacity})`,
          }}
        />
        <span className="relative z-10 pr-[3px] text-[9px] tabular-nums text-[#555]">
          {formatOI(callOI)}
        </span>
      </div>

      <div className="flex items-center justify-center text-[9px] tabular-nums text-[#555]">
        {row.call.iv != null ? row.call.iv.toFixed(1) : '--'}
      </div>

      <div
        className={`group/ce relative flex cursor-pointer items-center justify-end pr-1 ${
          activeCall ? 'bg-profit/15' : ''
        }`}
        onClick={() => onSelectQuote(row.call)}
      >
        <span
          className={`tabular-nums group-hover/ce:opacity-40 ${
            isATM ? 'text-[11px] font-semibold text-[#e0e0e0]' : 'text-[11px] text-[#b0b0b0]'
          }`}
        >
          {formatLTP(row.call.ltp)}
        </span>
        <div className="absolute inset-0 hidden items-center justify-center gap-0.5 group-hover/ce:flex">
          <button
            onClick={(event) => {
              event.stopPropagation()
              onViewChart(row.call)
            }}
            className={`flex h-[18px] w-[18px] items-center justify-center rounded-sm ${
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

      <div
        className={`flex items-center justify-center tabular-nums ${
          isATM
            ? 'bg-[rgba(229,83,75,0.08)] text-[10px] font-bold text-[#e53935]'
            : 'bg-[#232323] text-[10px] font-semibold text-[#666]'
        }`}
      >
        <span>{row.strike}</span>
      </div>

      <div
        className={`group/pe relative flex cursor-pointer items-center justify-start pl-1 ${
          activePut ? 'bg-loss/15' : ''
        }`}
        onClick={() => onSelectQuote(row.put)}
      >
        <span
          className={`tabular-nums group-hover/pe:opacity-40 ${
            isATM ? 'text-[11px] font-semibold text-[#e0e0e0]' : 'text-[11px] text-[#b0b0b0]'
          }`}
        >
          {formatLTP(row.put.ltp)}
        </span>
        <div className="absolute inset-0 hidden items-center justify-center gap-0.5 group-hover/pe:flex">
          <button
            onClick={(event) => {
              event.stopPropagation()
              onViewChart(row.put)
            }}
            className={`flex h-[18px] w-[18px] items-center justify-center rounded-sm ${
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

      <div className="flex items-center justify-center text-[9px] tabular-nums text-[#555]">
        {row.put.iv != null ? row.put.iv.toFixed(1) : '--'}
      </div>

      <div className="relative flex items-center justify-start overflow-hidden" style={{ borderRadius: 1 }}>
        <div
          className="absolute inset-y-0 left-0"
          style={{
            width: `${putOIPct}%`,
            background: `rgba(76,175,80,${oiBgOpacity})`,
          }}
        />
        <span className="relative z-10 pl-[3px] text-[9px] tabular-nums text-[#555]">
          {formatOI(putOI)}
        </span>
      </div>
    </div>
  )
})

export default function OptionsChainExpanded({ rows, maxOI, activeExpiry }: Props) {
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
    <div className="flex-1 overflow-auto">
      <div
        className="sticky top-0 z-10 grid items-center border-b border-[#2a2a2a] bg-bg-secondary"
        style={{ gridTemplateColumns: '44px 38px 1fr 50px 1fr 38px 44px' }}
      >
        <div className="py-[4px] text-center text-[8px] font-semibold uppercase tracking-[0.4px] text-[#555]">OI</div>
        <div className="py-[4px] text-center text-[8px] font-semibold uppercase tracking-[0.4px] text-[#555]">IV</div>
        <div className="py-[4px] pr-1 text-right text-[8px] font-semibold uppercase tracking-[0.4px] text-[#555]">CE</div>
        <div className="py-[4px] text-center text-[8px] font-semibold uppercase tracking-[0.4px] text-[#555]">Strike</div>
        <div className="py-[4px] pl-1 text-left text-[8px] font-semibold uppercase tracking-[0.4px] text-[#555]">PE</div>
        <div className="py-[4px] text-center text-[8px] font-semibold uppercase tracking-[0.4px] text-[#555]">IV</div>
        <div className="py-[4px] text-center text-[8px] font-semibold uppercase tracking-[0.4px] text-[#555]">OI</div>
      </div>

      {rows.map((row) => (
        <OptionsChainExpandedRow
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
  )
}
