import MarketWatch from '../components/MarketWatch'
import NiftyChart from '../components/NiftyChart'
import OptionsChain from '../components/OptionsChain'
import OrderTicket from '../components/OrderTicket'
import SignalPanel from '../components/SignalPanel'
import { useStore } from '../store/useStore'

function DepthCard() {
  const { selectedQuote } = useStore()

  return (
    <section className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
      <div className="mb-3 text-sm font-semibold text-text-primary">Market Depth</div>
      {selectedQuote ? (
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-xl bg-bg-primary p-3">
            <div className="text-text-muted">Bid</div>
            <div className="mt-1 text-lg font-semibold text-text-primary">{selectedQuote.bid?.toFixed(2) ?? '--'}</div>
            <div className="text-[11px] text-text-muted">Qty {selectedQuote.bid_qty ?? '--'}</div>
          </div>
          <div className="rounded-xl bg-bg-primary p-3">
            <div className="text-text-muted">Ask</div>
            <div className="mt-1 text-lg font-semibold text-text-primary">{selectedQuote.ask?.toFixed(2) ?? '--'}</div>
            <div className="text-[11px] text-text-muted">Qty {selectedQuote.ask_qty ?? '--'}</div>
          </div>
          <div className="rounded-xl bg-bg-primary p-3">
            <div className="text-text-muted">IV / OI</div>
            <div className="mt-1 text-text-primary">{selectedQuote.iv?.toFixed(2) ?? '--'} / {selectedQuote.oi?.toFixed(0) ?? '--'}</div>
          </div>
          <div className="rounded-xl bg-bg-primary p-3">
            <div className="text-text-muted">Greeks</div>
            <div className="mt-1 text-text-primary">Δ {selectedQuote.delta?.toFixed(2) ?? '--'} Γ {selectedQuote.gamma?.toFixed(3) ?? '--'}</div>
          </div>
        </div>
      ) : (
        <div className="text-xs text-text-muted">Select a contract to inspect depth.</div>
      )}
    </section>
  )
}

export default function Dashboard() {
  const { snapshot } = useStore()

  return (
    <div className="grid h-full grid-cols-[280px_minmax(0,1fr)_360px] gap-4 p-4">
      <MarketWatch />
      <div className="grid min-h-0 grid-rows-[minmax(280px,0.8fr)_minmax(0,1fr)] gap-4">
        <NiftyChart />
        <OptionsChain />
      </div>
      <div className="grid min-h-0 grid-rows-[auto_auto_1fr_auto] gap-4">
        {snapshot?.degraded ? (
          <div className="rounded-2xl border border-loss/30 bg-loss/10 px-4 py-3 text-xs text-loss">
            Market data is degraded: {snapshot.degraded_reason ?? 'unknown reason'}
          </div>
        ) : null}
        <SignalPanel />
        <DepthCard />
        <OrderTicket />
      </div>
    </div>
  )
}
