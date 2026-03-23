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

const OptionsChainCollapsedRow = memo(function OptionsChainCollapsedRow({
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
  const callOI = (row.call as Record<string, unknown>).oi_lakhs as number | null
  const putOI = (row.put as Record<string, unknown>).oi_lakhs as number | null
  const callOIWidth = callOI != null ? Math.min((callOI / maxOI) * 100, 100) : 0
  const putOIWidth = putOI != null ? Math.min((putOI / maxOI) * 100, 100) : 0
  const oiOpacity = isATM ? 0.55 : 0.4

  const callIsITM = atmStrike != null && !isATM && row.strike < atmStrike
  const putIsITM = atmStrike != null && !isATM && row.strike > atmStrike

  // Which quote is active for mobile action bar
  const activeQuote = activeCall ? row.call : activePut ? row.put : null
  const activeSide = activeCall ? 'CE' : activePut ? 'PE' : null

  return (
    <div ref={rowRef}>
      {/* Main row — taller on mobile for tap targets */}
      <div
        className={`group grid border-b border-[#222] px-2 transition-colors ${
          isATM
            ? 'border-l-2 border-l-[#e53935] bg-[rgba(229,83,75,0.05)]'
            : 'hover:bg-bg-hover'
        }`}
        style={{ gridTemplateColumns: '1fr 52px 1fr' }}
      >
        {/* CE cell */}
        <div
          className={`group/ce relative flex cursor-pointer items-center justify-end px-1 h-[44px] md:h-[36px] ${
            activeCall ? 'bg-profit/15' : ''
          }`}
          onClick={() => onSelectQuote(activeCall ? null : row.call)}
        >
          <span
            className={`tabular-nums text-[13px] md:text-[13px] leading-none md:group-hover/ce:opacity-40 ${
              isATM ? 'font-semibold text-[#e8e8e8]' : callIsITM ? 'text-[#888]' : 'text-[#b8b8b8]'
            }`}
          >
            {formatLTP(row.call.ltp)}
          </span>
          {/* Desktop hover buttons — hidden on mobile */}
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

        {/* Strike column — dark background spine, not clickable */}
        <div
          className={`flex items-center justify-center ${
            isATM
              ? 'bg-[rgba(229,83,75,0.12)]'
              : 'bg-[#1a1a1a]'
          }`}
        >
          <span
            className={`tabular-nums leading-none ${
              isATM
                ? 'text-[11px] font-bold text-[#ff6b6b]'
                : 'text-[10.5px] font-medium text-[#5a5a5a]'
            }`}
          >
            {row.strike}
          </span>
        </div>

        {/* PE cell */}
        <div
          className={`group/pe relative flex cursor-pointer items-center justify-start px-1 h-[44px] md:h-[36px] ${
            activePut ? 'bg-loss/15' : ''
          }`}
          onClick={() => onSelectQuote(activePut ? null : row.put)}
        >
          <span
            className={`tabular-nums text-[13px] md:text-[13px] leading-none md:group-hover/pe:opacity-40 ${
              isATM ? 'font-semibold text-[#e8e8e8]' : putIsITM ? 'text-[#888]' : 'text-[#b8b8b8]'
            }`}
          >
            {formatLTP(row.put.ltp)}
          </span>
          {/* Desktop hover buttons — hidden on mobile */}
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
      </div>

      {/* Thin OI bars below row */}
      <div className="grid px-2" style={{ gridTemplateColumns: '1fr 52px 1fr', height: '3px' }}>
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

      {/* Mobile action bar — slides in when a CE or PE is tapped */}
      {activeQuote && (
        <div className="flex items-center gap-2 border-b border-[#222] bg-[#1a1a1a] px-3 py-1.5 md:hidden">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <div className={`h-5 w-0.5 rounded-full ${activeSide === 'CE' ? 'bg-profit' : 'bg-loss'}`} />
            <div className="flex flex-col">
              <span className="text-[12px] font-semibold tabular-nums text-text-primary leading-tight">
                {row.strike} {activeSide}
              </span>
              <span className="text-[9px] tabular-nums text-text-muted leading-tight">
                LTP {formatLTP(activeQuote.ltp)}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => onViewChart(activeQuote)}
              className="flex h-[30px] w-[30px] items-center justify-center rounded-md bg-[#2a2a2a] text-[#aaa] active:bg-[#383838]"
            >
              <LineChart size={14} />
            </button>
            <button
              onClick={() => onOrder(activeQuote, 'BUY')}
              className="flex h-[30px] items-center rounded-md bg-btn-buy px-4 text-[11px] font-bold text-white active:brightness-90"
            >
              Buy
            </button>
            <button
              onClick={() => onOrder(activeQuote, 'SELL')}
              className="flex h-[30px] items-center rounded-md bg-btn-sell px-4 text-[11px] font-bold text-white active:brightness-90"
            >
              Sell
            </button>
          </div>
        </div>
      )}
    </div>
  )
})

export default function OptionsChainCollapsed({ rows, maxOI, atmStrike, activeExpiry }: Props) {
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
        <div className="grid px-2" style={{ gridTemplateColumns: '1fr 52px 1fr' }}>
          <div className="px-1 py-[5px] text-right text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">CE</div>
          <div className="flex items-center justify-center bg-[#1a1a1a] py-[5px] text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">Strike</div>
          <div className="px-1 py-[5px] text-left text-[9px] font-semibold uppercase tracking-[0.5px] text-[#555]">PE</div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {rows.map((row) => (
          <OptionsChainCollapsedRow
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
