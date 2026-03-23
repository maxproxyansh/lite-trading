import { memo, useEffect, useRef, type Ref } from 'react'
import { LineChart } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'

import type { OptionChainRow, OptionQuote } from '../lib/api'
import { useStore } from '../store/useStore'

interface Props {
  rows: OptionChainRow[]
  maxOI: number
  atmStrike: number | null
  activeExpiry: string | null
}

function formatLTP(ltp: number | null | undefined) {
  return ltp == null || ltp === 0 ? '--' : ltp.toFixed(2)
}

function formatOI(oi: number | null) {
  return oi == null ? '--' : `${Math.round(oi)}L`
}

const OptionsChainExpandedRow = memo(function OptionsChainExpandedRow({
  row,
  maxOI,
  atmStrike,
  selectedQuoteSymbol,
  activeChartSymbol,
  onSelectQuote,
  onOrder,
  onViewChart,
  rowRef,
}: {
  row: OptionChainRow
  maxOI: number
  atmStrike: number | null
  selectedQuoteSymbol: string | null
  activeChartSymbol: string | null
  onSelectQuote: (quote: OptionQuote | null) => void
  onOrder: (quote: OptionQuote, side: 'BUY' | 'SELL') => void
  onViewChart: (quote: OptionQuote) => void
  rowRef?: Ref<HTMLDivElement>
}) {
  const isATM = atmStrike != null ? row.strike === atmStrike : row.is_atm
  const activeCall = selectedQuoteSymbol === row.call.symbol
  const activePut = selectedQuoteSymbol === row.put.symbol
  const chartingCall = activeChartSymbol === row.call.symbol
  const chartingPut = activeChartSymbol === row.put.symbol
  const callOI = (row.call as Record<string, unknown>).oi_lakhs as number | null ?? null
  const putOI = (row.put as Record<string, unknown>).oi_lakhs as number | null ?? null
  const callOIPct = Math.min(100, callOI != null && maxOI > 0 ? (callOI / maxOI) * 100 : 0)
  const putOIPct = Math.min(100, putOI != null && maxOI > 0 ? (putOI / maxOI) * 100 : 0)
  const oiBgOpacity = isATM ? 0.55 : 0.4

  const callIsITM = atmStrike != null && !isATM && row.strike < atmStrike
  const putIsITM = atmStrike != null && !isATM && row.strike > atmStrike

  return (
    <div ref={rowRef}>
      <div
        className={`group grid border-b border-[#222] transition-colors ${
          isATM
            ? 'border-l-2 border-l-[#e53935] bg-[rgba(229,83,75,0.05)]'
            : 'hover:bg-bg-hover'
        }`}
        style={{ gridTemplateColumns: '44px 38px 1fr 52px 1fr 38px 44px', height: 36 }}
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
          {row.call.iv != null ? row.call.iv.toFixed(2) : '--'}
        </div>

        <div
          className={`group/ce relative flex cursor-pointer items-center justify-end pr-1 ${
            activeCall ? 'bg-profit/15' : ''
          }`}
          onClick={() => onSelectQuote(activeCall ? null : row.call)}
        >
          <span
            className={`tabular-nums text-[13px] leading-none md:group-hover/ce:opacity-40 ${
              isATM ? 'font-semibold text-[#e8e8e8]' : callIsITM ? 'text-[#888]' : 'text-[#b8b8b8]'
            }`}
          >
            {formatLTP(row.call.ltp)}
          </span>
          <div className="absolute inset-0 hidden items-center justify-center gap-1 md:group-hover/ce:flex">
            <button
              onClick={(event) => {
                event.stopPropagation()
                onViewChart(row.call)
              }}
              className={`flex h-[20px] w-[20px] items-center justify-center rounded ${
                chartingCall ? 'bg-brand text-bg-primary' : 'bg-[#2b2b2b] text-[#d0d0d0] hover:bg-[#383838]'
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
              className="h-[20px] w-[20px] rounded bg-btn-buy text-[9px] font-bold text-white hover:brightness-110"
            >
              B
            </button>
            <button
              onClick={(event) => {
                event.stopPropagation()
                onOrder(row.call, 'SELL')
              }}
              className="h-[20px] w-[20px] rounded bg-btn-sell text-[9px] font-bold text-white hover:brightness-110"
            >
              S
            </button>
          </div>
        </div>

        <div
          className={`flex items-center justify-center tabular-nums ${
            isATM
              ? 'bg-[rgba(229,83,75,0.12)] text-[11px] font-bold text-[#ff6b6b]'
              : 'bg-[#1a1a1a] text-[10.5px] font-medium text-[#5a5a5a]'
          }`}
        >
          <span>{row.strike}</span>
        </div>

        <div
          className={`group/pe relative flex cursor-pointer items-center justify-start pl-1 ${
            activePut ? 'bg-loss/15' : ''
          }`}
          onClick={() => onSelectQuote(activePut ? null : row.put)}
        >
          <span
            className={`tabular-nums text-[13px] leading-none md:group-hover/pe:opacity-40 ${
              isATM ? 'font-semibold text-[#e8e8e8]' : putIsITM ? 'text-[#888]' : 'text-[#b8b8b8]'
            }`}
          >
            {formatLTP(row.put.ltp)}
          </span>
          <div className="absolute inset-0 hidden items-center justify-center gap-1 md:group-hover/pe:flex">
            <button
              onClick={(event) => {
                event.stopPropagation()
                onViewChart(row.put)
              }}
              className={`flex h-[20px] w-[20px] items-center justify-center rounded ${
                chartingPut ? 'bg-brand text-bg-primary' : 'bg-[#2b2b2b] text-[#d0d0d0] hover:bg-[#383838]'
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
              className="h-[20px] w-[20px] rounded bg-btn-buy text-[9px] font-bold text-white hover:brightness-110"
            >
              B
            </button>
            <button
              onClick={(event) => {
                event.stopPropagation()
                onOrder(row.put, 'SELL')
              }}
              className="h-[20px] w-[20px] rounded bg-btn-sell text-[9px] font-bold text-white hover:brightness-110"
            >
              S
            </button>
          </div>
        </div>

        <div className="flex items-center justify-center text-[9px] tabular-nums text-[#555]">
          {row.put.iv != null ? row.put.iv.toFixed(2) : '--'}
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

      {/* Thin OI bars below row — matches collapsed view */}
      <div className="grid" style={{ gridTemplateColumns: '82px 1fr 52px 1fr 82px', height: '3px' }}>
        <div />
        <div className="relative overflow-hidden">
          <div
            className="absolute right-0 top-0 h-full"
            style={{
              width: `${callOIPct}%`,
              backgroundColor: `rgba(229,83,75,${oiBgOpacity})`,
            }}
          />
        </div>
        <div />
        <div className="relative overflow-hidden">
          <div
            className="absolute left-0 top-0 h-full"
            style={{
              width: `${putOIPct}%`,
              backgroundColor: `rgba(76,175,80,${oiBgOpacity})`,
            }}
          />
        </div>
        <div />
      </div>
    </div>
  )
})

export default function OptionsChainExpanded({ rows, maxOI, atmStrike, activeExpiry }: Props) {
  const { selectedQuoteSymbol, optionChartSymbol, setSelectedQuote, setOptionChartSymbol, openOrderModal } = useStore(useShallow((state) => ({
    selectedQuoteSymbol: state.selectedQuote?.symbol ?? null,
    optionChartSymbol: state.optionChartSymbol,
    setSelectedQuote: state.setSelectedQuote,
    setOptionChartSymbol: state.setOptionChartSymbol,
    openOrderModal: state.openOrderModal,
  })))
  const atmRef = useRef<HTMLDivElement>(null)
  const lastScrollKeyRef = useRef<string | null>(null)

  useEffect(() => {
    if (!atmRef.current || !activeExpiry || atmStrike == null) {
      return
    }
    const scrollKey = `${activeExpiry}:${atmStrike}:${rows.length}`
    if (lastScrollKeyRef.current === scrollKey) {
      return
    }
    atmRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' })
    lastScrollKeyRef.current = scrollKey
  }, [activeExpiry, atmStrike, rows.length])

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="sticky top-0 z-10 border-b border-[#222] bg-bg-secondary">
        <div
          className="grid"
          style={{ gridTemplateColumns: '44px 38px 1fr 52px 1fr 38px 44px' }}
        >
          <div className="py-[5px] text-center text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">OI</div>
          <div className="py-[5px] text-center text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">IV</div>
          <div className="px-1 py-[5px] text-right text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">CE</div>
          <div className="flex items-center justify-center bg-[#1a1a1a] py-[5px] text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">Strike</div>
          <div className="px-1 py-[5px] text-left text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">PE</div>
          <div className="py-[5px] text-center text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">IV</div>
          <div className="py-[5px] text-center text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">OI</div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {rows.map((row) => (
          // Live ATM comes from the latest spot, not the last REST chain snapshot.
          <OptionsChainExpandedRow
            key={row.strike}
            row={row}
            maxOI={maxOI}
            atmStrike={atmStrike}
            selectedQuoteSymbol={selectedQuoteSymbol}
            activeChartSymbol={optionChartSymbol}
            onSelectQuote={setSelectedQuote}
            onViewChart={(quote) => {
              setSelectedQuote(quote)
              setOptionChartSymbol(optionChartSymbol === quote.symbol ? null : quote.symbol)
            }}
            onOrder={openOrderModal}
            rowRef={(atmStrike != null ? row.strike === atmStrike : row.is_atm) ? atmRef : undefined}
          />
        ))}
      </div>
    </div>
  )
}
