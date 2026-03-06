import { useStore } from '../store/useStore'

const GLOBAL_INDICES = [
  { symbol: 'S&P 500', icon: '500', color: '#e74c3c' },
  { symbol: 'NASDAQ', icon: '100', color: '#2ecc71' },
  { symbol: 'DOW 30', icon: '30', color: '#3498db' },
  { symbol: 'Bitcoin', icon: 'B', color: '#f7931a' },
  { symbol: 'Ethereum', icon: 'E', color: '#627eea' },
  { symbol: 'Gold', icon: 'Au', color: '#f1c40f' },
  { symbol: 'Crude Oil', icon: 'CL', color: '#2c3e50' },
] as const

export default function TickerBar() {
  const { snapshot } = useStore()

  const items = [
    ...(snapshot
      ? [
          {
            symbol: 'NIFTY 50',
            icon: 'N50',
            color: '#387ed1',
            price: snapshot.spot,
            change: snapshot.change,
            changePct: snapshot.change_pct,
          },
          ...(snapshot.vix
            ? [
                {
                  symbol: 'INDIA VIX',
                  icon: 'VIX',
                  color: '#e67e22',
                  price: snapshot.vix,
                  change: 0,
                  changePct: 0,
                },
              ]
            : []),
        ]
      : []),
    ...GLOBAL_INDICES.map((idx) => ({
      ...idx,
      price: null as number | null,
      change: null as number | null,
      changePct: null as number | null,
    })),
  ]

  // Duplicate for seamless loop
  const doubled = [...items, ...items]

  return (
    <div className="relative h-7 shrink-0 overflow-hidden border-t border-border-primary bg-bg-primary">
      <div className="ticker-scroll absolute flex h-full items-center whitespace-nowrap">
        {doubled.map((item, i) => (
          <div key={`${item.symbol}-${i}`} className="flex items-center gap-2 px-4">
            <span
              className="flex h-4 w-4 items-center justify-center rounded-full text-[7px] font-bold text-white"
              style={{ backgroundColor: item.color }}
            >
              {item.icon.slice(0, 2)}
            </span>
            <span className="text-[11px] font-medium text-text-secondary">{item.symbol}</span>
            {item.price != null ? (
              <>
                <span className="text-[11px] tabular-nums text-text-primary">
                  {item.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                </span>
                {item.change != null && item.change !== 0 && (
                  <span
                    className={`text-[11px] tabular-nums ${item.change >= 0 ? 'text-profit' : 'text-loss'}`}
                  >
                    {item.change >= 0 ? '+' : ''}
                    {item.change.toFixed(2)}
                    {item.changePct != null ? ` (${item.changePct >= 0 ? '+' : ''}${item.changePct.toFixed(2)}%)` : ''}
                  </span>
                )}
              </>
            ) : (
              <span className="text-[11px] text-text-muted">--</span>
            )}
            <span className="text-text-muted/30">|</span>
          </div>
        ))}
      </div>
    </div>
  )
}
