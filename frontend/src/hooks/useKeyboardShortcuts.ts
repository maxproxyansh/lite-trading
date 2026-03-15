import { useEffect, useRef } from 'react'
import { useStore } from '../store/useStore'

const TIMEFRAME_MAP: Record<string, '1m' | '5m' | '15m' | '1h' | 'D' | 'W' | 'M'> = {
  h: '1h',
  d: 'D',
  w: 'W',
  m: 'M',
}

const CHORD_TIMEOUT = 300

export default function useKeyboardShortcuts() {
  const chordRef = useRef<{ key: string; timer: ReturnType<typeof setTimeout> } | null>(null)

  useEffect(() => {
    function clearChord() {
      if (chordRef.current) {
        clearTimeout(chordRef.current.timer)
        chordRef.current = null
      }
    }

    function commitTimeframe(tf: '1m' | '5m' | '15m' | '1h' | 'D' | 'W' | 'M') {
      clearChord()
      useStore.getState().setChartTimeframe(tf)
    }

    /** Resolve current anchor: optionChartSymbol if charting, else selectedQuote */
    function resolveAnchor(): { symbol: string; location: { rowIndex: number; side: 'call' | 'put' } } | null {
      const state = useStore.getState()
      const { chain, chainIndex } = state
      if (!chain) return null

      // Prefer the actively charted option
      const symbol = state.optionChartSymbol ?? state.selectedQuote?.symbol ?? null
      if (!symbol || !chainIndex[symbol]) return null
      return { symbol, location: chainIndex[symbol] }
    }

    function navigateStrike(direction: 'up' | 'down') {
      const anchor = resolveAnchor()
      if (!anchor) return false

      const state = useStore.getState()
      const nextRowIndex = direction === 'up' ? anchor.location.rowIndex - 1 : anchor.location.rowIndex + 1
      if (nextRowIndex < 0 || nextRowIndex >= state.chain!.rows.length) return false

      const nextRow = state.chain!.rows[nextRowIndex]
      const nextQuote = anchor.location.side === 'call' ? nextRow.call : nextRow.put
      state.setOptionChartSymbol(nextQuote.symbol)
      state.setSelectedQuote(nextQuote)
      return true
    }

    function switchCallPut(direction: 'left' | 'right') {
      const anchor = resolveAnchor()
      if (!anchor) return false

      const targetSide = direction === 'left' ? 'call' : 'put'
      if (anchor.location.side === targetSide) return false

      const state = useStore.getState()
      const row = state.chain!.rows[anchor.location.rowIndex]
      const nextQuote = targetSide === 'call' ? row.call : row.put
      state.setOptionChartSymbol(nextQuote.symbol)
      state.setSelectedQuote(nextQuote)
      return true
    }

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

      // Don't trigger on modifier combos (Cmd+C, Ctrl+V, etc.)
      if (e.metaKey || e.ctrlKey || e.altKey) return

      const key = e.key.toLowerCase()
      const state = useStore.getState()
      const quote = state.selectedQuote

      // --- Chord-aware timeframe shortcuts ---

      // Check if this completes a chord: "1" then "5" → 15m
      if (chordRef.current) {
        if (chordRef.current.key === '1' && key === '5') {
          commitTimeframe('15m')
          e.preventDefault()
          return
        }
        // Not a valid chord — commit the pending "1" as 1m, then handle this key below
        commitTimeframe('1m')
      }

      // Start a chord if "1" is pressed (could be 1m or start of 15m)
      if (key === '1') {
        chordRef.current = {
          key: '1',
          timer: setTimeout(() => {
            // Timeout elapsed without "5" — commit as 1m
            if (chordRef.current?.key === '1') {
              commitTimeframe('1m')
            }
          }, CHORD_TIMEOUT),
        }
        e.preventDefault()
        return
      }

      // Direct timeframe keys
      if (key === '5') {
        commitTimeframe('5m')
        e.preventDefault()
        return
      }

      if (TIMEFRAME_MAP[key] && key !== 'm') {
        commitTimeframe(TIMEFRAME_MAP[key])
        e.preventDefault()
        return
      }

      // --- Arrow key strike navigation (when option chart is active OR a quote is selected) ---
      if (state.optionChartSymbol || state.selectedQuote) {
        if (e.key === 'ArrowUp') {
          if (navigateStrike('up')) e.preventDefault()
          return
        }
        if (e.key === 'ArrowDown') {
          if (navigateStrike('down')) e.preventDefault()
          return
        }
        if (e.key === 'ArrowLeft') {
          if (switchCallPut('left')) e.preventDefault()
          return
        }
        if (e.key === 'ArrowRight') {
          if (switchCallPut('right')) e.preventDefault()
          return
        }
      }

      // --- Existing shortcuts ---

      // B — Buy selected option
      if (key === 'b') {
        if (quote) {
          state.openOrderModal(quote, 'BUY')
          e.preventDefault()
        }
        return
      }

      // S — Sell selected option
      if (key === 's') {
        if (quote) {
          state.openOrderModal(quote, 'SELL')
          e.preventDefault()
        }
        return
      }

      // C — Toggle option chart for selected quote
      if (key === 'c') {
        if (quote) {
          const current = state.optionChartSymbol
          state.setOptionChartSymbol(current === quote.symbol ? null : quote.symbol)
          e.preventDefault()
        }
        return
      }

      // E — Toggle expanded/collapsed chain view
      if (key === 'e') {
        state.setChainView(state.chainView === 'collapsed' ? 'expanded' : 'collapsed')
        e.preventDefault()
        return
      }

      // M — Monthly timeframe (check after E to avoid conflict, handle M separately since it's also a letter)
      if (key === 'm') {
        commitTimeframe('M')
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

    // Use capture phase so arrow keys are intercepted before lightweight-charts consumes them
    window.addEventListener('keydown', handler, true)
    return () => {
      window.removeEventListener('keydown', handler, true)
      clearChord()
    }
  }, [])
}
