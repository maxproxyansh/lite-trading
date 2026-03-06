import { ChevronDown, ChevronUp } from 'lucide-react'

import { useStore } from '../store/useStore'

export default function OptionsChain() {
  const { chain, snapshot, selectedQuote, setSelectedQuote, selectedExpiry, setSelectedExpiry } = useStore()

  if (!chain || !snapshot) {
    return (
      <section className="rounded-2xl border border-border-primary bg-bg-secondary p-4 text-sm text-text-muted">
        Waiting for option chain...
      </section>
    )
  }

  return (
    <section className="flex h-full flex-col rounded-2xl border border-border-primary bg-bg-secondary">
      <div className="flex items-center justify-between border-b border-border-primary px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-text-primary">Options Chain</div>
          <div className="text-[11px] text-text-muted">NIFTY weekly contracts with live bid/ask and greeks</div>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedExpiry ?? chain.snapshot.active_expiry ?? ''}
            onChange={(event) => setSelectedExpiry(event.target.value)}
            className="rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none"
          >
            {(snapshot.expiries || []).map((expiry) => (
              <option key={expiry} value={expiry}>{expiry}</option>
            ))}
          </select>
          <div className="text-right">
            <div className="text-[11px] text-text-muted">Spot</div>
            <div className="tabular-nums text-sm text-text-primary">{snapshot.spot.toFixed(2)}</div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full table-fixed text-xs">
          <thead className="sticky top-0 z-10 bg-bg-secondary text-text-muted">
            <tr>
              <th className="px-2 py-2 text-right font-medium">Bid</th>
              <th className="px-2 py-2 text-right font-medium">LTP</th>
              <th className="px-2 py-2 text-right font-medium">Ask</th>
              <th className="px-2 py-2 text-right font-medium">IV</th>
              <th className="px-2 py-2 text-center font-medium">Strike</th>
              <th className="px-2 py-2 text-left font-medium">IV</th>
              <th className="px-2 py-2 text-left font-medium">Bid</th>
              <th className="px-2 py-2 text-left font-medium">LTP</th>
              <th className="px-2 py-2 text-left font-medium">Ask</th>
            </tr>
          </thead>
          <tbody>
            {chain.rows.map((row) => {
              const activeCall = selectedQuote?.symbol === row.call.symbol
              const activePut = selectedQuote?.symbol === row.put.symbol
              return (
                <tr key={row.strike} className={`border-t border-border-primary/50 ${row.is_atm ? 'bg-signal/8' : ''}`}>
                  <td className={`px-2 py-2 text-right ${activeCall ? 'bg-profit/10' : ''}`}>{row.call.bid?.toFixed(2) ?? '--'}</td>
                  <td
                    className={`cursor-pointer px-2 py-2 text-right font-semibold text-profit ${activeCall ? 'bg-profit/15' : 'hover:bg-profit/8'}`}
                    onClick={() => setSelectedQuote(row.call)}
                  >
                    {row.call.ltp.toFixed(2)}
                  </td>
                  <td className={`px-2 py-2 text-right ${activeCall ? 'bg-profit/10' : ''}`}>{row.call.ask?.toFixed(2) ?? '--'}</td>
                  <td className="px-2 py-2 text-right">{row.call.iv?.toFixed(1) ?? '--'}</td>
                  <td className="px-2 py-2 text-center font-semibold text-text-primary">
                    <div className="inline-flex items-center gap-1 rounded-full bg-bg-primary px-2 py-1">
                      {row.is_atm ? <ChevronUp size={12} className="text-signal" /> : <ChevronDown size={12} className="text-text-muted" />}
                      {row.strike}
                    </div>
                  </td>
                  <td className="px-2 py-2 text-left">{row.put.iv?.toFixed(1) ?? '--'}</td>
                  <td className={`px-2 py-2 text-left ${activePut ? 'bg-loss/10' : ''}`}>{row.put.bid?.toFixed(2) ?? '--'}</td>
                  <td
                    className={`cursor-pointer px-2 py-2 text-left font-semibold text-loss ${activePut ? 'bg-loss/15' : 'hover:bg-loss/8'}`}
                    onClick={() => setSelectedQuote(row.put)}
                  >
                    {row.put.ltp.toFixed(2)}
                  </td>
                  <td className={`px-2 py-2 text-left ${activePut ? 'bg-loss/10' : ''}`}>{row.put.ask?.toFixed(2) ?? '--'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
