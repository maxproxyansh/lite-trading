import { useStore } from '../store/useStore'

type ChainQuote = {
  symbol: string
  ltp: number
  iv?: number | null
  oi_lakhs?: number | null
}

export default function OptionsChain() {
  const { chain, snapshot, selectedQuote, setSelectedQuote, selectedExpiry, setSelectedExpiry } = useStore()

  if (!chain || !snapshot) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-text-muted">
        Waiting for option chain…
      </div>
    )
  }

  const getOILakhs = (quote: ChainQuote) => quote.oi_lakhs ?? null

  const maxOI = Math.max(
    ...chain.rows.flatMap((row) => [
      getOILakhs(row.call as ChainQuote) ?? 0,
      getOILakhs(row.put as ChainQuote) ?? 0,
    ]),
    1,
  )

  const formatOI = (oi: number | null) => {
    if (oi == null) return '--'
    return oi.toFixed(1)
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-primary px-4 py-2">
        <div>
          <span className="text-[11px] text-text-muted uppercase tracking-wide font-normal">Options Chain</span>
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
        <table className="w-full table-fixed text-[12px] tabular-nums">
          <thead className="sticky top-0 z-10 bg-bg-secondary text-[11px] text-text-muted">
            <tr>
              <th className="w-[15%] px-2 py-[3px] text-right text-[11px] text-text-muted uppercase tracking-wide font-normal">OI(L)</th>
              <th className="w-[12%] px-2 py-[3px] text-right text-[11px] text-text-muted uppercase tracking-wide font-normal">IV%</th>
              <th className="w-[12%] px-2 py-[3px] text-right text-[11px] text-text-muted uppercase tracking-wide font-normal">LTP</th>
              <th className="w-[14%] px-1 py-[3px] text-center text-[11px] text-text-muted uppercase tracking-wide font-normal">Strike</th>
              <th className="w-[12%] px-2 py-[3px] text-left text-[11px] text-text-muted uppercase tracking-wide font-normal">LTP</th>
              <th className="w-[12%] px-2 py-[3px] text-left text-[11px] text-text-muted uppercase tracking-wide font-normal">IV%</th>
              <th className="w-[15%] px-2 py-[3px] text-left text-[11px] text-text-muted uppercase tracking-wide font-normal">OI(L)</th>
            </tr>
          </thead>
          <tbody>
            {chain.rows.map((row) => {
              const activeCall = selectedQuote?.symbol === row.call.symbol
              const activePut = selectedQuote?.symbol === row.put.symbol
              const callOI = getOILakhs(row.call as ChainQuote)
              const putOI = getOILakhs(row.put as ChainQuote)
              const callOIPct = Math.min(60, callOI != null ? (callOI / maxOI) * 100 : 0)
              const putOIPct = Math.min(60, putOI != null ? (putOI / maxOI) * 100 : 0)

              return (
                <tr
                  key={row.strike}
                  className={`border-t border-border-secondary/40 h-[28px] ${row.is_atm ? 'bg-[rgba(229,83,75,0.08)]' : ''}`}
                >
                  {/* CE OI */}
                  <td className="px-2 py-[2px] text-right tabular-nums">
                    <div className="relative overflow-hidden">
                      <div
                        className="absolute inset-y-0 right-0 bg-profit/25"
                        style={{ width: `${callOIPct}%` }}
                      />
                      <span className="relative z-10">{formatOI(callOI)}</span>
                    </div>
                  </td>
                  {/* CE IV */}
                  <td className="px-2 py-[2px] text-right tabular-nums text-text-muted">
                    {row.call.iv?.toFixed(1) ?? '--'}
                  </td>
                  {/* CE LTP */}
                  <td
                    className={`cursor-pointer px-2 py-[2px] text-right tabular-nums font-medium text-[#4bae4f] ${
                      activeCall ? 'bg-profit/15' : 'hover:bg-profit/6'
                    }`}
                    onClick={() => setSelectedQuote(row.call)}
                  >
                    {row.call.ltp.toFixed(2)}
                  </td>

                  {/* Strike */}
                  <td className="px-2 py-[2px] text-center">
                    <span className={`font-medium ${row.is_atm ? 'text-[#e5534b]' : 'text-text-primary'}`}>
                      {row.strike}
                    </span>
                  </td>

                  {/* PE LTP */}
                  <td
                    className={`cursor-pointer px-2 py-[2px] text-left tabular-nums font-medium text-[#d43725] ${
                      activePut ? 'bg-loss/15' : 'hover:bg-loss/6'
                    }`}
                    onClick={() => setSelectedQuote(row.put)}
                  >
                    {row.put.ltp.toFixed(2)}
                  </td>
                  {/* PE IV */}
                  <td className="px-2 py-[2px] text-left tabular-nums text-text-muted">
                    {row.put.iv?.toFixed(1) ?? '--'}
                  </td>
                  {/* PE OI */}
                  <td className="px-2 py-[2px] text-left tabular-nums">
                    <div className="relative overflow-hidden">
                      <div
                        className="absolute inset-y-0 left-0 bg-loss/25"
                        style={{ width: `${putOIPct}%` }}
                      />
                      <span className="relative z-10">{formatOI(putOI)}</span>
                    </div>
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
