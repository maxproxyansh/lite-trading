import { memo, useEffect, useRef } from 'react'
import type { IndicatorConfig, IndicatorType } from '../../lib/chart/types'
import { OVERLAY_INDICATORS, OSCILLATOR_INDICATORS } from '../../lib/chart/types'

interface Props {
  indicators: IndicatorConfig[]
  onToggle: (id: string) => void
  onClose: () => void
}

const LABELS: Record<IndicatorType, string> = {
  ema: 'EMA', sma: 'SMA', bb: 'Bollinger', vwap: 'VWAP', supertrend: 'Supertrend', ichimoku: 'Ichimoku',
  rsi: 'RSI', macd: 'MACD', adx: 'ADX',
}

export const IndicatorPanel = memo(function IndicatorPanel({ indicators, onToggle, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  const overlays = indicators.filter((i) => OVERLAY_INDICATORS.includes(i.type))
  const oscillators = indicators.filter((i) => OSCILLATOR_INDICATORS.includes(i.type))

  return (
    <div ref={ref} className="absolute right-0 top-[28px] z-30 w-[260px] rounded-lg border border-[#3a3a3a] bg-[#222] shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
      <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-[#666]">Overlay</div>
      <div className="flex flex-wrap gap-1 px-2 pb-2">
        {overlays.map((ind) => (
          <button key={ind.id} onClick={() => onToggle(ind.id)}
            className={`rounded px-2.5 py-1 text-[11px] transition-colors ${
              ind.enabled ? 'border border-brand/30 bg-brand/15 text-brand' : 'border border-[#3a3a3a] bg-[#2a2a2a] text-[#999] hover:border-[#555] hover:text-[#ccc]'
            }`}>
            {LABELS[ind.type]}{ind.enabled ? ' ✓' : ''}
          </button>
        ))}
      </div>
      <div className="mx-2 border-t border-[#333]" />
      <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-[#666]">Oscillator</div>
      <div className="flex flex-wrap gap-1 px-2 pb-2">
        {oscillators.map((ind) => (
          <button key={ind.id} onClick={() => onToggle(ind.id)}
            className={`rounded px-2.5 py-1 text-[11px] transition-colors ${
              ind.enabled ? 'border border-brand/30 bg-brand/15 text-brand' : 'border border-[#3a3a3a] bg-[#2a2a2a] text-[#999] hover:border-[#555] hover:text-[#ccc]'
            }`}>
          {LABELS[ind.type]}{ind.enabled ? ' ✓' : ''}
          </button>
        ))}
      </div>
    </div>
  )
})
