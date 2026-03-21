# NIFTY PiP Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a floating Picture-in-Picture pill that shows live NIFTY spot price when the user leaves the Lite PWA on Android Chrome.

**Architecture:** Document PiP API opens a separate browser window rendered as a floating overlay. We create a React portal into that window, subscribe to the existing Zustand store, and inject plain CSS (Tailwind doesn't work in the PiP document). The existing WebSocket keeps updating the store — the PiP portal gets updates automatically.

**Tech Stack:** React 19, Document Picture-in-Picture API, Zustand, createPortal (react-dom)

**Spec:** `docs/superpowers/specs/2026-03-21-nifty-pip-widget-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/types/document-pip.d.ts` | Create | TypeScript type declarations for `documentPictureInPicture` API |
| `frontend/src/hooks/usePiP.ts` | Create | Hook: open/close PiP window, feature detection, React portal lifecycle |
| `frontend/src/components/PiPWidget.tsx` | Create | Pill UI rendered inside PiP window — spot price, optional P&L, accent border |
| `frontend/src/components/PiPButton.tsx` | Create | Float button shown in Header on supported browsers |
| `frontend/src/components/Header.tsx` | Modify | Add `<PiPButton />` next to spot price display |

---

### Task 1: TypeScript Type Declarations

**Files:**
- Create: `frontend/src/types/document-pip.d.ts`

- [ ] **Step 1: Create the type declaration file**

The Document PiP API is not in TypeScript's DOM lib. We need global type declarations so TS doesn't error on `documentPictureInPicture`.

Note: The `frontend/src/types/` directory does not exist yet — it will be created when writing the file.

```ts
// frontend/src/types/document-pip.d.ts

interface DocumentPictureInPictureOptions {
  width?: number
  height?: number
}

interface DocumentPictureInPicture extends EventTarget {
  requestWindow(options?: DocumentPictureInPictureOptions): Promise<Window>
  readonly window: Window | null
}

interface Window {
  documentPictureInPicture?: DocumentPictureInPicture
}

declare const documentPictureInPicture: DocumentPictureInPicture | undefined
```

This is a script-mode `.d.ts` file (no `export`). Top-level interface declarations augment the global scope automatically. No `declare global` or `export {}` needed — avoids conflicts with `verbatimModuleSyntax: true` in tsconfig.

- [ ] **Step 2: Verify TypeScript picks up the declaration**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors related to `documentPictureInPicture`. The `"include": ["src"]` in `tsconfig.app.json` will pick up `src/types/` automatically.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/document-pip.d.ts
git commit -m "feat(pip): add TypeScript declarations for Document PiP API"
```

---

### Task 2: usePiP Hook

**Files:**
- Create: `frontend/src/hooks/usePiP.ts`

- [ ] **Step 1: Create the hook**

This hook manages the entire PiP lifecycle: feature detection, opening the window, injecting styles, creating the portal target, and cleanup on close.

```tsx
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
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/usePiP.ts
git commit -m "feat(pip): add usePiP hook for Document PiP lifecycle"
```

---

### Task 3: PiPWidget Component

**Files:**
- Create: `frontend/src/components/PiPWidget.tsx`

- [ ] **Step 1: Create the widget component**

This is the pill UI that renders inside the PiP window's portal. It reads from the Zustand store directly. Uses plain CSS classes (injected by the hook), NOT Tailwind.

```tsx
// frontend/src/components/PiPWidget.tsx
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '../store/useStore'

export default function PiPWidget() {
  const { snapshot, wsStatus, positions } = useStore(
    useShallow((state) => ({
      snapshot: state.snapshot,
      wsStatus: state.wsStatus,
      positions: state.positions,
    }))
  )

  const spot = snapshot?.spot ?? 0
  const change = snapshot?.change ?? 0
  const changePct = snapshot?.change_pct ?? 0
  const isPositive = change >= 0
  const isStale = wsStatus !== 'connected'

  const showPnl = localStorage.getItem('pip-show-pnl') === 'true'
  const totalPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0)
  const hasPositions = positions.length > 0

  const pillClass = [
    'pip-pill',
    !isPositive && 'negative',
    isStale && 'stale',
  ].filter(Boolean).join(' ')

  return (
    <div className={pillClass}>
      <div className="pip-row">
        <span className="pip-label">NIFTY</span>
        <span className="pip-price">
          {spot > 0 ? spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
        </span>
        {spot > 0 && (
          <span className={`pip-change ${isPositive ? 'positive' : 'negative'}`}>
            {isPositive ? '+' : ''}{changePct.toFixed(2)}%
          </span>
        )}
      </div>
      {showPnl && hasPositions && (
        <div className="pip-row">
          <span className="pip-pnl-label">P&L</span>
          <span className={`pip-pnl-value ${totalPnl >= 0 ? 'positive' : 'negative'}`}>
            {totalPnl >= 0 ? '+' : ''}{'\u20B9'}{Math.abs(totalPnl).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
          </span>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PiPWidget.tsx
git commit -m "feat(pip): add PiPWidget pill component"
```

---

### Task 4: PiPButton Component

**Files:**
- Create: `frontend/src/components/PiPButton.tsx`

- [ ] **Step 1: Create the button component**

A small icon button that opens the PiP. Renders the portal when PiP is open. Only shown on supported browsers.

```tsx
// frontend/src/components/PiPButton.tsx
import { createPortal } from 'react-dom'
import { usePiP, isPiPSupported } from '../hooks/usePiP'
import PiPWidget from './PiPWidget'

export default function PiPButton() {
  const { isOpen, portalTarget, open, close } = usePiP()

  if (!isPiPSupported) return null

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation() // Prevent bubbling to parent spot price div
    if (isOpen) close()
    else open()
  }

  return (
    <>
      <button
        onClick={handleClick}
        className="flex items-center justify-center rounded p-0.5 text-text-muted transition-colors hover:text-text-primary"
        title={isOpen ? 'Close floating price' : 'Float price'}
      >
        <svg
          viewBox="0 0 24 24"
          className="h-3.5 w-3.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {isOpen ? (
            <>
              <rect x="2" y="2" width="20" height="20" rx="2" />
              <line x1="9" y1="9" x2="15" y2="15" />
              <line x1="15" y1="9" x2="9" y2="15" />
            </>
          ) : (
            <>
              <rect x="2" y="2" width="20" height="20" rx="2" />
              <rect x="12" y="10" width="8" height="8" rx="1" />
            </>
          )}
        </svg>
      </button>
      {isOpen && portalTarget && createPortal(<PiPWidget />, portalTarget)}
    </>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PiPButton.tsx
git commit -m "feat(pip): add PiPButton with portal rendering"
```

---

### Task 5: Integrate PiPButton into Header

**Files:**
- Modify: `frontend/src/components/Header.tsx:47-61` (spot price display area)

- [ ] **Step 1: Add the PiPButton import and render it next to the spot price**

In `Header.tsx`, add the import at the top:

```tsx
import PiPButton from '../components/PiPButton'
```

Then insert `<PiPButton />` right after the spot price change span, inside the `div` at line 47 but after the closing of the change `span` (line 60). Place it after the closing `)}` on line 60, before the closing `</div>` on line 61. Show only on mobile (`md:hidden`).

The spot price section (lines 47-61) should become:

```tsx
        <div
          className={`flex items-center gap-1 rounded px-1 py-0.5 transition-colors ${optionChartSymbol ? 'cursor-pointer hover:bg-bg-hover' : ''}`}
          onClick={optionChartSymbol ? () => setOptionChartSymbol(null) : undefined}
          title={optionChartSymbol ? 'Back to NIFTY chart' : undefined}
        >
          <span className="text-[12px] text-text-muted">NIFTY 50</span>
          <span className={`text-[15px] font-semibold tabular-nums ${snapshot && snapshot.spot > 0 && snapshot.change >= 0 ? 'text-profit' : snapshot && snapshot.spot > 0 ? 'text-loss' : 'text-text-primary'}`}>
            {snapshot && snapshot.spot > 0 ? snapshot.spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '--'}
          </span>
          {snapshot && snapshot.spot > 0 && (snapshot.change !== 0 || snapshot.change_pct !== 0) && (
            <span className={`text-[11px] md:text-[12px] tabular-nums ${snapshot.change >= 0 ? 'text-profit' : 'text-loss'}`}>
              {snapshot.change >= 0 ? '+' : ''}{snapshot.change.toFixed(2)} ({snapshot.change_pct.toFixed(2)}%)
            </span>
          )}
          <span className="md:hidden"><PiPButton /></span>
        </div>
```

- [ ] **Step 2: Verify TypeScript compiles and dev server renders**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No type errors.

Run: `cd /Users/proxy/trading/lite/frontend && npx vite build 2>&1 | tail -10`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Header.tsx
git commit -m "feat(pip): integrate PiP button into Header on mobile"
```

---

### Task 6: Manual Testing on Android

- [ ] **Step 1: Deploy and test on Android Chrome**

1. Deploy to Vercel (or use `vite preview` with ngrok for local testing)
2. Open on Android Chrome (116+)
3. Verify the PiP button appears next to NIFTY spot price on mobile viewport
4. Verify button is hidden on desktop (`md:hidden`)
5. Tap the button — PiP window should open as a floating pill
6. Switch to another app — pill should stay visible
7. Verify spot price updates in real-time inside the pill
8. Verify accent border is green when positive, red when negative
9. Verify dimmed opacity when WebSocket disconnects
10. Tap the pill — should close PiP and return to Lite
11. Test with `localStorage.setItem('pip-show-pnl', 'true')` — verify P&L row appears when positions exist

- [ ] **Step 2: Commit any fixes from testing**
