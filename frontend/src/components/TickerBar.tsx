import { useStore } from '../store/useStore'

export default function TickerBar() {
  const snapshot = useStore((state) => state.snapshot)

  // Build items only from sources that have actual data
  const items: {
    symbol: string
    icon: string
    color: string
    price: number
    change: number
    changePct: number
  }[] = []

  if (snapshot && snapshot.spot && snapshot.spot > 0) {
    items.push({
      symbol: 'NIFTY 50',
      icon: 'N50',
      color: '#387ed1',
      price: snapshot.spot,
      change: snapshot.change ?? 0,
      changePct: snapshot.change_pct ?? 0,
    })
  }

  if (snapshot && snapshot.vix && snapshot.vix > 0) {
    items.push({
      symbol: 'INDIA VIX',
      icon: 'VIX',
      color: '#e67e22',
      price: snapshot.vix,
      change: 0,
      changePct: 0,
    })
  }

  // If no items have data, hide the entire ticker bar
  if (items.length === 0) {
    return null
  }

  // Duplicate for seamless marquee loop (animation translates -50%)
  const doubled = [...items, ...items]

  return (
    <div className="relative hidden h-7 shrink-0 overflow-hidden border-t border-border-primary bg-bg-primary md:flex">
      <div className="ticker-scroll absolute flex h-full w-max items-center whitespace-nowrap">
        {doubled.map((item, i) => (
          <div key={`${item.symbol}-${i}`} className="flex items-center gap-2 px-4">
            <span
              className="flex h-4 w-4 items-center justify-center rounded-full text-[7px] font-bold text-white"
              style={{ backgroundColor: item.color }}
            >
              {item.icon.slice(0, 2)}
            </span>
            <span className="text-[11px] font-medium text-text-secondary">{item.symbol}</span>
            <span className="text-[11px] tabular-nums text-text-primary">
              {item.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
            </span>
            {item.change !== 0 && (
              <span
                className={`text-[11px] tabular-nums ${item.change >= 0 ? 'text-profit' : 'text-loss'}`}
              >
                {item.change >= 0 ? '+' : ''}
                {item.change.toFixed(2)}
                {` (${item.changePct >= 0 ? '+' : ''}${item.changePct.toFixed(2)}%)`}
              </span>
            )}
            <span className="text-text-muted/30">|</span>
          </div>
        ))}
      </div>
    </div>
  )
}
