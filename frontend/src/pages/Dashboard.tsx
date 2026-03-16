import { useEffect, useState } from 'react'
import { BarChart3, Grid2x2 } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'

import MobileOptionsChain from '../components/MobileOptionsChain'
import NiftyChart from '../components/NiftyChart'
import OptionsPanel from '../components/OptionsPanel'
import { useStore } from '../store/useStore'

type MobileView = 'chart' | 'chain'

export default function Dashboard() {
  const { degraded, degradedReason, optionChartSymbol } = useStore(useShallow((state) => ({
    degraded: state.snapshot?.degraded ?? false,
    degradedReason: state.snapshot?.degraded_reason ?? null,
    optionChartSymbol: state.optionChartSymbol,
  })))
  const [mobileView, setMobileView] = useState<MobileView>('chart')

  // When an option chart is selected (from chain's chart button), switch to chart view
  useEffect(() => {
    if (optionChartSymbol) {
      setMobileView('chart')
    }
  }, [optionChartSymbol])

  return (
    <div className="flex h-full">
      {/* Desktop options panel — hidden on mobile */}
      <OptionsPanel />

      <div className="flex flex-1 flex-col overflow-hidden">
        {degraded && (
          <div className="border-b border-loss/30 bg-loss/10 px-3 py-1.5 text-xs text-loss">
            Market data degraded: {degradedReason ?? 'unknown'}
          </div>
        )}

        {/* Mobile view toggle — only on mobile */}
        <div className="flex border-b border-border-secondary md:hidden">
          <button
            onClick={() => setMobileView('chart')}
            className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors ${
              mobileView === 'chart'
                ? 'border-b-2 border-brand text-brand'
                : 'text-text-muted'
            }`}
          >
            <BarChart3 size={13} />
            Chart
          </button>
          <button
            onClick={() => setMobileView('chain')}
            className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors ${
              mobileView === 'chain'
                ? 'border-b-2 border-brand text-brand'
                : 'text-text-muted'
            }`}
          >
            <Grid2x2 size={13} />
            Options
          </button>
        </div>

        {/* Desktop: always show chart. Mobile: toggle between chart and chain */}
        <div className={`flex-1 min-h-0 ${mobileView === 'chain' ? 'hidden md:flex md:flex-col' : 'flex flex-col'}`}>
          <NiftyChart />
        </div>

        {mobileView === 'chain' && (
          <div className="flex flex-1 min-h-0 flex-col md:hidden">
            <MobileOptionsChain />
          </div>
        )}
      </div>

      {/* Mobile order ticket — no longer needed, B/S buttons are in the chart toolbar */}
    </div>
  )
}
