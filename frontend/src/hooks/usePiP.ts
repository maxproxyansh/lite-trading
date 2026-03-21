// frontend/src/hooks/usePiP.ts
import { useState, useCallback, useEffect, useRef } from 'react'

export const isPiPSupported = typeof window !== 'undefined' && 'documentPictureInPicture' in window

const PIP_STYLES = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: transparent;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  }
  .pip-pill {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    width: 100%;
    height: 100%;
    padding: 6px 12px;
    background: #1a1a2e;
    border-radius: 24px;
    border: 4px solid #22c55e;
    cursor: pointer;
    transition: border-color 0.3s;
  }
  .pip-pill.negative { border-color: #ef4444; }
  .pip-pill.stale { opacity: 0.5; }
  .pip-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .pip-label {
    font-size: 11px;
    font-weight: 600;
    color: #94a3b8;
    letter-spacing: 0.5px;
  }
  .pip-price {
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
    font-variant-numeric: tabular-nums;
  }
  .pip-change {
    font-size: 11px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .pip-change.positive { color: #22c55e; }
  .pip-change.negative { color: #ef4444; }
  .pip-pnl-label {
    font-size: 10px;
    color: #94a3b8;
  }
  .pip-pnl-value {
    font-size: 12px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .pip-pnl-value.positive { color: #22c55e; }
  .pip-pnl-value.negative { color: #ef4444; }
`

interface UsePiPReturn {
  isOpen: boolean
  portalTarget: HTMLElement | null
  open: () => Promise<void>
  close: () => void
}

export function usePiP(): UsePiPReturn {
  const [isOpen, setIsOpen] = useState(false)
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null)
  const pipWindowRef = useRef<Window | null>(null)

  const close = useCallback(() => {
    if (pipWindowRef.current) {
      pipWindowRef.current.close()
      pipWindowRef.current = null
    }
    setPortalTarget(null)
    setIsOpen(false)
  }, [])

  const open = useCallback(async () => {
    if (!isPiPSupported || !window.documentPictureInPicture) return

    // Close any existing PiP window
    if (pipWindowRef.current) {
      pipWindowRef.current.close()
    }

    try {
      const pipWindow = await window.documentPictureInPicture.requestWindow({
        width: 240,
        height: 64,
      })

      pipWindowRef.current = pipWindow

      // Inject styles
      const style = pipWindow.document.createElement('style')
      style.textContent = PIP_STYLES
      pipWindow.document.head.appendChild(style)

      // Create portal target
      const container = pipWindow.document.createElement('div')
      container.id = 'pip-root'
      pipWindow.document.body.appendChild(container)

      // Tap to return
      container.addEventListener('click', () => {
        close()
        window.focus()
      })

      // Cleanup on PiP close
      pipWindow.addEventListener('pagehide', () => {
        pipWindowRef.current = null
        setPortalTarget(null)
        setIsOpen(false)
      })

      setPortalTarget(container)
      setIsOpen(true)
    } catch (err) {
      console.warn('PiP failed to open:', err)
    }
  }, [close])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pipWindowRef.current) {
        pipWindowRef.current.close()
        pipWindowRef.current = null
      }
    }
  }, [])

  return { isOpen, portalTarget, open, close }
}
