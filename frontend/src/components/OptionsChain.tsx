import { ChevronDown, ChevronUp } from 'lucide-react'

import { useStore } from '../store/useStore'

export default function OptionsChain() {
  const { chain, snapshot, selectedQuote, setSelectedQuote, selectedExpiry, setSelectedExpiry } = useStore()

  if (!chain || !snapshot) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-text-muted">
        Waiting for option chain\u2026
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-primary px-4 py-2">
        <div>
          <span className="text-sm font-medium text-text-primary">Options Chain</span>
          <span className="ml-2 text-[11px] text-text-muted">NIFTY weekly contracts</span>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedExpiry ?? chain.snapshot.active_expiry ?? ''}
            onChange={(e) => setSelectedExpiry(e.target.value)}
            className="cursor-pointer rounded border border-border-primary bg-bg-tertiary px-2 py-1 text-xs text-text-primary outline-none"
          >
            {(snapshot.expiries || []).map((expiry) => (
              <option key={expiry} value={expiry}>{expiry}</option>
            ))}
          </select>
          <div className="text-right text-xs">
            <span className="text-text-muted">Spot </span>
            <span className="tabular-nums font-medium text-text-primary">{snapshot.spot.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full table-fixed text-xs">
          <thead className="sticky top-0 z-10 bg-bg-secondary text-[11px] text-text-muted">
            <tr>
              <th className="w-[11%] px-2 py-2 text-right font-medium">Bid</th>
              <th className="w-[11%] px-2 py-2 text-right font-medium">LTP</th>
              <th className="w-[11%] px-2 py-2 text-right font-medium">Ask</th>
              <th className="w-[11%] px-2 py-2 text-right font-medium">IV</th>
              <th className="w-[12%] px-2 py-2 text-center font-medium">Strike</th>
              <th className="w-[11%] px-2 py-2 text-left font-medium">IV</th>
              <th className="w-[11%] px-2 py-2 text-left font-medium">Bid</th>
              <th className="w-[11%] px-2 py-2 text-left font-medium">LTP</th>
              <th className="w-[11%] px-2 py-2 text-left font-medium">Ask</th>
            </tr>
          </thead>
          <tbody>
            {chain.rows.map((row) => {
              const activeCall = selectedQuote?.symbol === row.call.symbol
              const activePut = selectedQuote?.symbol === row.put.symbol
              return (
                <tr
                  key={row.strike}
                  className={`border-t border-border-secondary/40 ${row.is_atm ? 'bg-signal/8' : ''}`}
                >
                  {/* CE side */}
                  <td className={`px-2 py-1.5 text-right tabular-nums ${activeCall ? 'bg-profit/8' : ''}`}>
                    {row.call.bid?.toFixed(2) ?? '--'}
                  </td>
                  <td
                    className={`cursor-pointer px-2 py-1.5 text-right tabular-nums font-medium text-profit ${
                      activeCall ? 'bg-profit/15' : 'hover:bg-profit/6'
                    }`}
                    onClick={() => setSelectedQuote(row.call)}
                  >
                    {row.call.ltp.toFixed(2)}
                  </td>
                  <td className={`px-2 py-1.5 text-right tabular-nums ${activeCall ? 'bg-profit/8' : ''}`}>
                    {row.call.ask?.toFixed(2) ?? '--'}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums text-text-muted">
                    {row.call.iv?.toFixed(1) ?? '--'}
                  </td>

                  {/* Strike */}
                  <td className="px-2 py-1.5 text-center">
                    <span className="inline-flex items-center gap-1 text-text-primary font-medium">
                      {row.is_atm ? (
                        <ChevronUp size={11} className="text-signal" />
                      ) : (
                        <ChevronDown size={11} className="text-text-muted" />
                      )}
                      {row.strike}
                    </span>
                  </td>

                  {/* PE side */}
                  <td className="px-2 py-1.5 text-left tabular-nums text-text-muted">
                    {row.put.iv?.toFixed(1) ?? '--'}
                  </td>
                  <td className={`px-2 py-1.5 text-left tabular-nums ${activePut ? 'bg-loss/8' : ''}`}>
                    {row.put.bid?.toFixed(2) ?? '--'}
                  </td>
                  <td
                    className={`cursor-pointer px-2 py-1.5 text-left tabular-nums font-medium text-loss ${
                      activePut ? 'bg-loss/15' : 'hover:bg-loss/6'
                    }`}
                    onClick={() => setSelectedQuote(row.put)}
                  >
                    {row.put.ltp.toFixed(2)}
                  </td>
                  <td className={`px-2 py-1.5 text-left tabular-nums ${activePut ? 'bg-loss/8' : ''}`}>
                    {row.put.ask?.toFixed(2) ?? '--'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
