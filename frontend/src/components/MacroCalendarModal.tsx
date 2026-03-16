import { memo, useEffect, useState } from 'react'
import { X } from 'lucide-react'

interface Props {
  onClose: () => void
}

function buildWidgetUrl(showAll: boolean): string {
  const config = {
    colorTheme: 'dark',
    isTransparent: true,
    width: '100%',
    height: '100%',
    importanceFilter: showAll ? '-1,0,1' : '0,1',
    countryFilter: 'in,us,eu,gb,jp,cn',
  }
  return `https://s.tradingview.com/embed-widget/events/?locale=en#${encodeURIComponent(JSON.stringify(config))}`
}

export const MacroCalendarModal = memo(function MacroCalendarModal({ onClose }: Props) {
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', handleKey, true)
    return () => window.removeEventListener('keydown', handleKey, true)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      <div
        className="relative w-[780px] max-w-[95vw] h-[85vh] max-h-[85vh] flex flex-col rounded-xl border border-[#333] bg-[#1a1a1a] shadow-[0_24px_80px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#2a2a2a] bg-[#1a1a1a]/95 px-5 py-3 backdrop-blur-sm rounded-t-xl">
          <div>
            <h2 className="text-[14px] font-semibold text-[#e0e0e0]">Macro Calendar</h2>
            <p className="mt-0.5 text-[11px] text-[#666]">Economic events & data releases</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowAll((v) => !v)}
              className={`px-2.5 py-1 rounded text-[11px] transition-colors ${
                showAll
                  ? 'bg-[#2a2a2a] text-[#999]'
                  : 'bg-[#3b82f6]/15 text-[#3b82f6]'
              }`}
            >
              {showAll ? 'All events' : 'Important only'}
            </button>
            <button
              onClick={onClose}
              className="flex h-6 w-6 items-center justify-center rounded-md text-[#666] transition-colors hover:bg-[#2a2a2a] hover:text-[#ccc]"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* TradingView Widget */}
        <div className="flex-1 overflow-hidden rounded-b-xl">
          <iframe
            key={showAll ? 'all' : 'important'}
            src={buildWidgetUrl(showAll)}
            className="w-full h-full border-0"
            title="Economic Calendar"
            sandbox="allow-scripts allow-same-origin allow-popups"
          />
        </div>
      </div>
    </div>
  )
})
