import { useEffect } from 'react'
import { useStore } from '../store/useStore'

export default function useKeyboardShortcuts() {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const target = e.target as HTMLElement
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable

      // Escape always works — close modals
      if (e.key === 'Escape') {
        const { orderModal, closeOrderModal } = useStore.getState()
        if (orderModal?.isOpen) {
          closeOrderModal()
          e.preventDefault()
        }
        return
      }

      // Don't trigger shortcuts when typing in inputs
      if (isInput) return

      const state = useStore.getState()
      const quote = state.selectedQuote

      // B — Buy selected option
      if (e.key === 'b' || e.key === 'B') {
        if (quote) {
          state.openOrderModal(quote, 'BUY')
          e.preventDefault()
        }
        return
      }

      // S — Sell selected option
      if (e.key === 's' || e.key === 'S') {
        if (quote) {
          state.openOrderModal(quote, 'SELL')
          e.preventDefault()
        }
        return
      }

      // C — Toggle option chart for selected quote
      if (e.key === 'c' || e.key === 'C') {
        if (quote) {
          const current = state.optionChartSymbol
          state.setOptionChartSymbol(current === quote.symbol ? null : quote.symbol)
          e.preventDefault()
        }
        return
      }

      // E — Toggle expanded/collapsed chain view
      if (e.key === 'e' || e.key === 'E') {
        state.setChainView(state.chainView === 'collapsed' ? 'expanded' : 'collapsed')
        e.preventDefault()
        return
      }

      // [ — Collapse options panel, ] — Expand options panel
      if (e.key === '[') {
        state.setChainPanelOpen(false)
        e.preventDefault()
        return
      }
      if (e.key === ']') {
        state.setChainPanelOpen(true)
        e.preventDefault()
        return
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
}
