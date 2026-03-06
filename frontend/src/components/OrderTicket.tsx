import { useState } from 'react'

import { submitOrder } from '../lib/api'
import { useStore } from '../store/useStore'

const ORDER_TYPES = ['MARKET', 'LIMIT', 'SL', 'SL-M'] as const
const PRODUCTS = ['NRML', 'MIS'] as const

export default function OrderTicket() {
  const { selectedQuote, selectedPortfolioId, latestSignal, addToast } = useStore()
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [orderType, setOrderType] = useState<(typeof ORDER_TYPES)[number]>('MARKET')
  const [product, setProduct] = useState<(typeof PRODUCTS)[number]>('NRML')
  const [lots, setLots] = useState(1)
  const [price, setPrice] = useState('')
  const [triggerPrice, setTriggerPrice] = useState('')
  const [loading, setLoading] = useState(false)

  const defaultPrice = selectedQuote ? (side === 'BUY' ? selectedQuote.ask ?? selectedQuote.ltp : selectedQuote.bid ?? selectedQuote.ltp) : 0
  const estimatedValue = (price ? Number(price) : defaultPrice) * lots * 25

  const canSubmit = selectedQuote && (orderType === 'MARKET' || price)

  return (
    <section className="rounded-2xl border border-border-primary bg-bg-secondary p-4">
      <div className="mb-3">
        <div className="text-sm font-semibold text-text-primary">Order Ticket</div>
        <div className="text-[11px] text-text-muted">Single-leg options with market, limit and stop variants</div>
      </div>

      <div className="mb-3 rounded-xl bg-bg-primary p-3 text-xs text-text-secondary">
        {selectedQuote ? (
          <>
            <div className="mb-1 font-semibold text-text-primary">{selectedQuote.symbol}</div>
            <div className="grid grid-cols-3 gap-2">
              <div>Bid <span className="tabular-nums text-text-primary">{selectedQuote.bid?.toFixed(2) ?? '--'}</span></div>
              <div>LTP <span className="tabular-nums text-text-primary">{selectedQuote.ltp.toFixed(2)}</span></div>
              <div>Ask <span className="tabular-nums text-text-primary">{selectedQuote.ask?.toFixed(2) ?? '--'}</span></div>
            </div>
          </>
        ) : (
          <div>Select a contract from Marketwatch or the option chain.</div>
        )}
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2">
        <button onClick={() => setSide('BUY')} className={`rounded-xl px-3 py-2 text-sm font-semibold ${side === 'BUY' ? 'bg-profit text-white' : 'bg-bg-primary text-text-secondary'}`}>BUY</button>
        <button onClick={() => setSide('SELL')} className={`rounded-xl px-3 py-2 text-sm font-semibold ${side === 'SELL' ? 'bg-loss text-white' : 'bg-bg-primary text-text-secondary'}`}>SELL</button>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2">
        <label className="text-[11px] text-text-muted">
          Order Type
          <select value={orderType} onChange={(event) => setOrderType(event.target.value as typeof orderType)} className="mt-1 w-full rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none">
            {ORDER_TYPES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="text-[11px] text-text-muted">
          Product
          <select value={product} onChange={(event) => setProduct(event.target.value as typeof product)} className="mt-1 w-full rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none">
            {PRODUCTS.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </div>

      <div className="mb-3 grid grid-cols-3 gap-2">
        <label className="text-[11px] text-text-muted">
          Lots
          <input type="number" min={1} max={200} value={lots} onChange={(event) => setLots(Math.max(1, Number(event.target.value) || 1))} className="mt-1 w-full rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none" />
        </label>
        <label className="text-[11px] text-text-muted">
          Price
          <input type="number" step="0.05" value={price} onChange={(event) => setPrice(event.target.value)} placeholder={defaultPrice ? defaultPrice.toFixed(2) : '--'} className="mt-1 w-full rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none" />
        </label>
        <label className="text-[11px] text-text-muted">
          Trigger
          <input type="number" step="0.05" value={triggerPrice} onChange={(event) => setTriggerPrice(event.target.value)} placeholder="Optional" className="mt-1 w-full rounded-xl border border-border-primary bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none" />
        </label>
      </div>

      <div className="mb-4 rounded-xl border border-border-primary bg-bg-primary p-3 text-xs text-text-secondary">
        <div className="mb-1 flex justify-between">
          <span>Portfolio</span>
          <span className="font-medium text-text-primary uppercase">{selectedPortfolioId}</span>
        </div>
        <div className="mb-1 flex justify-between">
          <span>Signal attached</span>
          <span className="font-medium text-text-primary">{latestSignal?.id ? 'Yes' : 'No'}</span>
        </div>
        <div className="flex justify-between">
          <span>Est. notional</span>
          <span className="tabular-nums text-text-primary">{estimatedValue.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
        </div>
      </div>

      <button
        disabled={!canSubmit || loading || !selectedQuote}
        onClick={async () => {
          if (!selectedQuote) return
          setLoading(true)
          try {
            const order = await submitOrder({
              portfolio_id: selectedPortfolioId,
              symbol: selectedQuote.symbol,
              expiry: selectedQuote.expiry,
              strike: selectedQuote.strike,
              option_type: selectedQuote.option_type,
              side,
              order_type: orderType,
              product,
              validity: 'DAY',
              lots,
              price: price ? Number(price) : null,
              trigger_price: triggerPrice ? Number(triggerPrice) : null,
              signal_id: latestSignal?.id ?? null,
              idempotency_key: crypto.randomUUID(),
            })
            addToast('success', `Order ${order.status}: ${order.side} ${order.symbol} x ${order.quantity}`)
            setPrice('')
            setTriggerPrice('')
          } catch (error) {
            addToast('error', error instanceof Error ? error.message : 'Order failed')
          } finally {
            setLoading(false)
          }
        }}
        className={`w-full rounded-xl px-4 py-3 text-sm font-semibold text-white transition ${
          side === 'BUY' ? 'bg-profit hover:opacity-90' : 'bg-loss hover:opacity-90'
        } disabled:cursor-not-allowed disabled:opacity-40`}
      >
        {loading ? 'Submitting…' : `${side} ${selectedQuote?.option_type ?? 'Option'}`}
      </button>
    </section>
  )
}
