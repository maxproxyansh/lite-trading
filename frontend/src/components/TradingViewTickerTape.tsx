import { useEffect, useRef } from 'react'

export default function TradingViewTickerTape() {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    containerRef.current.innerHTML = ''

    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js'
    script.async = true
    script.type = 'text/javascript'
    script.innerHTML = JSON.stringify({
      symbols: [
        { proName: "NSE:NIFTY", title: "NIFTY 50" },
        { proName: "NSE:BANKNIFTY", title: "BANK NIFTY" },
        { proName: "BSE:SENSEX", title: "SENSEX" },
        { proName: "NSE:INDIAVIX", title: "INDIA VIX" },
      ],
      showSymbolLogo: false,
      isTransparent: true,
      displayMode: "compact",
      colorTheme: "dark",
      locale: "en"
    })

    containerRef.current.appendChild(script)

    return () => {
      if (containerRef.current) containerRef.current.innerHTML = ''
    }
  }, [])

  return (
    <div className="hidden md:block border-t border-border-primary">
      <div className="tradingview-widget-container" ref={containerRef}>
        <div className="tradingview-widget-container__widget"></div>
      </div>
    </div>
  )
}
