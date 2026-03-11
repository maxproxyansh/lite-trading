import { useEffect, useRef } from 'react'

interface Props {
  symbol?: string
}

export default function TradingViewTechnicalAnalysis({ symbol = "NSE:NIFTY" }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    container.innerHTML = ''

    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js'
    script.async = true
    script.type = 'text/javascript'
    script.innerHTML = JSON.stringify({
      interval: "1h",
      width: "100%",
      isTransparent: true,
      height: "100%",
      symbol,
      showIntervalTabs: true,
      displayMode: "single",
      colorTheme: "dark",
      locale: "en"
    })

    container.appendChild(script)

    return () => {
      container.innerHTML = ''
    }
  }, [symbol])

  return (
    <div className="tradingview-widget-container" ref={containerRef} style={{ height: '100%', minHeight: 250 }}>
      <div className="tradingview-widget-container__widget" style={{ height: '100%' }}></div>
    </div>
  )
}
