import { useEffect, useState } from 'react'

import { submitOrder } from '../lib/api'
import { useStore } from '../store/useStore'

const ORDER_TYPES = ['MARKET', 'LIMIT', 'SL', 'SL-M'] as const
const PRODUCTS = ['NRML', 'MIS'] as const
const NIFTY_LOT_SIZE = 65

type OrderType = (typeof ORDER_TYPES)[number]
type Product = (typeof PRODUCTS)[number]

export default function OrderModal() {
  const { orderModal, closeOrderModal, selectedPortfolioId, latestSignal, addToast } = useStore()

  const [orderType, setOrderType] = useState<OrderType>('MARKET')
  const [product, setProduct] = useState<Product>('NRML')
  const [lots, setLots] = useState(1)
  const [price, setPrice] = useState('')
  const [triggerPrice, setTriggerPrice] = useState('')
  const [loading, setLoading] = useState(false)

  // Reset form when modal opens
  useEffect(() => {
    if (orderModal?.isOpen) {
      setOrderType('MARKET')
      setProduct('NRML')
      setLots(1)
      setPrice('')
      setTriggerPrice('')
      setLoading(false)
    }
  }, [orderModal?.isOpen])

  // Close on Escape
  useEffect(() => {
    if (!orderModal?.isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeOrderModal()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [orderModal?.isOpen, closeOrderModal])

  if (!orderModal?.isOpen || !orderModal.quote) return null

  const { quote, side } = orderModal
  const isBuy = side === 'BUY'
  const showPrice = orderType === 'LIMIT' || orderType === 'SL' || orderType === 'SL-M'
  const showTrigger = orderType === 'SL' || orderType === 'SL-M'

  const defaultPrice = quote.ask ?? quote.ltp
  const effectivePrice = price ? Number(price) : defaultPrice
  const estimatedValue = effectivePrice * lots * NIFTY_LOT_SIZE
  const canSubmit = orderType === 'MARKET' || price

  async function handleSubmit() {
    if (!quote) return
    setLoading(true)
    try {
      const order = await submitOrder({
        portfolio_id: selectedPortfolioId,
        symbol: quote.symbol,
        expiry: quote.expiry,
        strike: quote.strike,
        option_type: quote.option_type,
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
      addToast('success', `${order.status}: ${side} ${order.symbol} x ${order.quantity}`)
      closeOrderModal()
    } catch (error) {
      addToast('error', error instanceof Error ? error.message : 'Order failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) closeOrderModal() }}
    >
      <div className="w-full max-w-[420px] mx-4 bg-bg-secondary border border-border-primary rounded-sm shadow-2xl animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-primary">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">{quote.symbol}</span>
            <span className="text-xs text-text-muted">{quote.strike} {quote.option_type}</span>
            <span className={`px-1.5 py-0.5 text-[10px] font-bold text-white rounded-sm ${isBuy ? 'bg-profit' : 'bg-loss'}`}>
              {side}
            </span>
          </div>
          <button
            onClick={closeOrderModal}
            className="text-text-muted hover:text-text-primary text-lg leading-none px-1"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-3">
          {/* Lots */}
          <div>
            <label className="block text-[10px] text-text-muted uppercase mb-0.5">Lots</label>
            <input
              type="number"
              min={1}
              max={200}
              value={lots}
              onChange={(e) => setLots(Math.max(1, Math.min(200, Number(e.target.value) || 1)))}
              className="w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1.5 text-sm tabular-nums text-text-primary outline-none"
            />
            <div className="text-[10px] text-text-muted mt-0.5">= {lots * NIFTY_LOT_SIZE} units</div>
          </div>

          {/* Order Type */}
          <div>
            <label className="block text-[10px] text-text-muted uppercase mb-0.5">Order Type</label>
            <div className="inline-flex rounded-sm border border-border-primary overflow-hidden w-full">
              {ORDER_TYPES.map((t) => (
                <button
                  key={t}
                  onClick={() => setOrderType(t)}
                  className={`flex-1 px-2 py-1.5 text-xs font-medium transition-colors ${
                    orderType === t
                      ? (isBuy ? 'bg-profit text-white' : 'bg-loss text-white')
                      : 'bg-bg-primary text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Price */}
          {showPrice && (
            <div>
              <label className="block text-[10px] text-text-muted uppercase mb-0.5">Price</label>
              <input
                type="number"
                step="0.05"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder={defaultPrice.toFixed(2)}
                className="w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1.5 text-sm tabular-nums text-text-primary outline-none placeholder:text-text-muted"
              />
            </div>
          )}

          {/* Trigger Price */}
          {showTrigger && (
            <div>
              <label className="block text-[10px] text-text-muted uppercase mb-0.5">Trigger Price</label>
              <input
                type="number"
                step="0.05"
                value={triggerPrice}
                onChange={(e) => setTriggerPrice(e.target.value)}
                placeholder="--"
                className="w-full rounded-sm border border-border-primary bg-bg-primary px-2 py-1.5 text-sm tabular-nums text-text-primary outline-none placeholder:text-text-muted"
              />
            </div>
          )}

          {/* Product */}
          <div>
            <label className="block text-[10px] text-text-muted uppercase mb-0.5">Product</label>
            <div className="inline-flex rounded-sm border border-border-primary overflow-hidden">
              {PRODUCTS.map((p) => (
                <button
                  key={p}
                  onClick={() => setProduct(p)}
                  className={`px-4 py-1.5 text-xs font-medium transition-colors ${
                    product === p
                      ? (isBuy ? 'bg-profit text-white' : 'bg-loss text-white')
                      : 'bg-bg-primary text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Estimated Value */}
          <div className="flex justify-between border-t border-border-secondary pt-2 text-[11px] text-text-muted">
            <span>Est. value</span>
            <span className="tabular-nums text-text-primary">
              {estimatedValue.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
            </span>
          </div>

          {/* Submit */}
          <button
            disabled={!canSubmit || loading}
            onClick={handleSubmit}
            className={`w-full rounded-sm py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30 ${
              isBuy ? 'bg-profit' : 'bg-loss'
            }`}
          >
            {loading ? 'Submitting...' : side}
          </button>
        </div>
      </div>
    </div>
  )
}
