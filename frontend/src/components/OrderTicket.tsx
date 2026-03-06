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
    <div className="p-3">
      <div className="mb-2 text-xs font-medium text-text-secondary">Order Ticket</div>

      {/* Contract */}
      <div className="mb-3 rounded bg-bg-primary px-3 py-2 text-xs">
        {selectedQuote ? (
          <>
            <div className="mb-1 font-medium text-text-primary">{selectedQuote.symbol}</div>
            <div className="flex gap-4 tabular-nums text-text-muted">
              <span>B {selectedQuote.bid?.toFixed(2) ?? '--'}</span>
              <span className="text-text-primary">{selectedQuote.ltp.toFixed(2)}</span>
              <span>A {selectedQuote.ask?.toFixed(2) ?? '--'}</span>
            </div>
          </>
        ) : (
          <span className="text-text-muted">Select a contract from the chain</span>
        )}
      </div>

      {/* Side */}
      <div className="mb-3 grid grid-cols-2 gap-1">
        <button
          onClick={() => setSide('BUY')}
          className={`rounded py-2 text-xs font-semibold transition-colors ${
            side === 'BUY' ? 'bg-profit text-white' : 'bg-bg-primary text-text-secondary hover:text-text-primary'
          }`}
        >
          BUY
        </button>
        <button
          onClick={() => setSide('SELL')}
          className={`rounded py-2 text-xs font-semibold transition-colors ${
            side === 'SELL' ? 'bg-loss text-white' : 'bg-bg-primary text-text-secondary hover:text-text-primary'
          }`}
        >
          SELL
        </button>
      </div>

      {/* Type + Product */}
      <div className="mb-3 grid grid-cols-2 gap-2">
        <label className="text-[10px] text-text-muted">
          Type
          <select
            value={orderType}
            onChange={(e) => setOrderType(e.target.value as typeof orderType)}
            className="mt-0.5 w-full rounded border border-border-primary bg-bg-primary px-2 py-1.5 text-xs text-text-primary outline-none"
          >
            {ORDER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="text-[10px] text-text-muted">
          Product
          <select
            value={product}
            onChange={(e) => setProduct(e.target.value as typeof product)}
            className="mt-0.5 w-full rounded border border-border-primary bg-bg-primary px-2 py-1.5 text-xs text-text-primary outline-none"
          >
            {PRODUCTS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
      </div>

      {/* Lots + Price + Trigger */}
      <div className="mb-3 grid grid-cols-3 gap-2">
        <label className="text-[10px] text-text-muted">
          Lots
          <input
            type="number"
            min={1}
            max={200}
            value={lots}
            onChange={(e) => setLots(Math.max(1, Number(e.target.value) || 1))}
            className="mt-0.5 w-full rounded border border-border-primary bg-bg-primary px-2 py-1.5 text-xs tabular-nums text-text-primary outline-none"
          />
        </label>
        <label className="text-[10px] text-text-muted">
          Price
          <input
            type="number"
            step="0.05"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder={defaultPrice ? defaultPrice.toFixed(2) : '--'}
            className="mt-0.5 w-full rounded border border-border-primary bg-bg-primary px-2 py-1.5 text-xs tabular-nums text-text-primary outline-none placeholder:text-text-muted"
          />
        </label>
        <label className="text-[10px] text-text-muted">
          Trigger
          <input
            type="number"
            step="0.05"
            value={triggerPrice}
            onChange={(e) => setTriggerPrice(e.target.value)}
            placeholder="--"
            className="mt-0.5 w-full rounded border border-border-primary bg-bg-primary px-2 py-1.5 text-xs tabular-nums text-text-primary outline-none placeholder:text-text-muted"
          />
        </label>
      </div>

      {/* Summary */}
      <div className="mb-3 space-y-1 border-t border-border-secondary pt-2 text-[11px] text-text-muted">
        <div className="flex justify-between">
          <span>Portfolio</span>
          <span className="font-medium text-text-primary">{selectedPortfolioId}</span>
        </div>
        <div className="flex justify-between">
          <span>Signal</span>
          <span className="text-text-primary">{latestSignal?.id ? 'Attached' : 'None'}</span>
        </div>
        <div className="flex justify-between">
          <span>Est. value</span>
          <span className="tabular-nums text-text-primary">{estimatedValue.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
        </div>
      </div>

      {/* Submit */}
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
            addToast('success', `${order.status}: ${order.side} ${order.symbol} x ${order.quantity}`)
            setPrice('')
            setTriggerPrice('')
          } catch (error) {
            addToast('error', error instanceof Error ? error.message : 'Order failed')
          } finally {
            setLoading(false)
          }
        }}
        className={`w-full rounded py-2.5 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30 ${
          side === 'BUY' ? 'bg-profit' : 'bg-loss'
        }`}
      >
        {loading ? 'Submitting\u2026' : `${side} ${selectedQuote?.option_type ?? 'Option'}`}
      </button>
    </div>
  )
}
