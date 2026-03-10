import { useEffect, useState } from 'react'

import { submitOrder } from '../lib/api'
import { useStore } from '../store/useStore'

const ORDER_TYPES = ['MARKET', 'LIMIT', 'SL', 'SL-M'] as const
const PRODUCTS = ['NRML', 'MIS'] as const
const NIFTY_LOT_SIZE = 65

export default function OrderTicket() {
  const { selectedQuote, selectedPortfolioId, latestSignal, addToast } = useStore()
  const [optionType, setOptionType] = useState<'CE' | 'PE'>('CE')
  const [orderType, setOrderType] = useState<(typeof ORDER_TYPES)[number]>('MARKET')
  const [product, setProduct] = useState<(typeof PRODUCTS)[number]>('NRML')
  const [lots, setLots] = useState(1)
  const [price, setPrice] = useState('')
  const [triggerPrice, setTriggerPrice] = useState('')
  const [loading, setLoading] = useState(false)

  // Auto-detect CE/PE from selected quote
  useEffect(() => {
    if (selectedQuote?.option_type) {
      setOptionType(selectedQuote.option_type as 'CE' | 'PE')
    }
  }, [selectedQuote])

  const defaultPrice = selectedQuote ? (selectedQuote.ask ?? selectedQuote.ltp) : 0
  const estimatedValue = (price ? Number(price) : defaultPrice) * lots * NIFTY_LOT_SIZE

  const canSubmit = selectedQuote && (orderType === 'MARKET' || price)

  return (
    <div className="border-b border-border-primary p-2">
      <div className="mb-2 text-[10px] text-text-muted uppercase">Order Ticket</div>

      {/* Contract */}
      <div className="mb-2 rounded-sm bg-bg-primary px-2 py-1.5 text-[12px]">
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

      {/* CE / PE compact pill toggle */}
      <div className="mb-2">
        <div className="inline-flex rounded-sm border border-border-primary overflow-hidden">
          <button
            onClick={() => setOptionType('CE')}
            className={`px-4 py-1.5 text-xs font-medium transition-colors ${
              optionType === 'CE' ? 'bg-profit text-white' : 'bg-bg-primary text-text-muted hover:text-text-secondary'
            }`}
          >CE</button>
          <button
            onClick={() => setOptionType('PE')}
            className={`px-4 py-1.5 text-xs font-medium transition-colors ${
              optionType === 'PE' ? 'bg-loss text-white' : 'bg-bg-primary text-text-muted hover:text-text-secondary'
            }`}
          >PE</button>
        </div>
      </div>

      {/* Type + Product */}
      <div className="mb-2 grid grid-cols-2 gap-2">
        <label className="text-[10px] text-text-muted uppercase">
          Type
          <select
            value={orderType}
            onChange={(e) => setOrderType(e.target.value as typeof orderType)}
            className="mt-0.5 w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1.5 text-[12px] text-text-primary outline-none"
          >
            {ORDER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="text-[10px] text-text-muted uppercase">
          Product
          <select
            value={product}
            onChange={(e) => setProduct(e.target.value as typeof product)}
            className="mt-0.5 w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1.5 text-[12px] text-text-primary outline-none"
          >
            {PRODUCTS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
      </div>

      {/* Lots + Price + Trigger */}
      <div className="mb-2 grid grid-cols-3 gap-2">
        <label className="text-[10px] text-text-muted uppercase">
          Lots
          <input
            type="number"
            min={1}
            max={200}
            value={lots}
            onChange={(e) => setLots(Math.max(1, Number(e.target.value) || 1))}
            className="mt-0.5 w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1.5 text-[12px] tabular-nums text-text-primary outline-none"
          />
        </label>
        <label className="text-[10px] text-text-muted uppercase">
          Price
          <input
            type="number"
            step="0.05"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder={defaultPrice ? defaultPrice.toFixed(2) : '--'}
            className="mt-0.5 w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1.5 text-[12px] tabular-nums text-text-primary outline-none placeholder:text-text-muted"
          />
        </label>
        <label className="text-[10px] text-text-muted uppercase">
          Trigger
          <input
            type="number"
            step="0.05"
            value={triggerPrice}
            onChange={(e) => setTriggerPrice(e.target.value)}
            placeholder="--"
            className="mt-0.5 w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1.5 text-[12px] tabular-nums text-text-primary outline-none placeholder:text-text-muted"
          />
        </label>
      </div>

      {/* Summary */}
      <div className="mb-2 space-y-1 border-t border-border-secondary pt-2 text-[11px] text-text-muted">
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
              option_type: optionType,
              side: 'BUY',
              order_type: orderType,
              product,
              validity: 'DAY',
              lots,
              price: price ? Number(price) : null,
              trigger_price: triggerPrice ? Number(triggerPrice) : null,
              signal_id: latestSignal?.id ?? null,
              idempotency_key: crypto.randomUUID(),
            })
            addToast('success', `${order.status}: BUY ${order.symbol} x ${order.quantity}`)
            setPrice('')
            setTriggerPrice('')
          } catch (error) {
            addToast('error', error instanceof Error ? error.message : 'Order failed')
          } finally {
            setLoading(false)
          }
        }}
        className={`w-full rounded-sm py-1.5 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30 ${
          optionType === 'CE' ? 'bg-profit' : 'bg-loss'
        }`}
      >
        {loading ? 'Submitting...' : `BUY ${optionType}`}
      </button>

      {!selectedQuote && (
        <p className="text-xs text-text-muted text-center mt-2">
          ← Select a contract from the chain
        </p>
      )}
    </div>
  )
}
