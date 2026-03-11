# Dashboard Layout Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Dashboard into a full-height chart with a left-side options chain panel that has collapsed/expanded views, inline B/S buttons, expiry tabs, ITM/ATM/OTM filter, and per-option chart button.

**Architecture:** Remove the right sidebar entirely. The chart becomes full-height in the main area. Options chain moves to a left-side panel (next to the nav sidebar) that can toggle between collapsed (LTP | Strike | LTP) and expanded (OI + IV + LTP | Strike | LTP + IV + OI) views, and can fully collapse via a `>` toggle. Expiries become horizontal pill tabs. A filter bar offers ITM/ATM/OTM/Full views. Orders are placed via the existing OrderModal popup.

**Tech Stack:** React 19, Tailwind CSS v4, Zustand, lightweight-charts v4

**CRITICAL RULES (from CLAUDE.md):**
- Tailwind v4: ALL custom CSS must be inside `@layer base`. Unlayered CSS overrides Tailwind utilities.
- NO rounded corners (use `rounded-sm` = 2px max). Sharp/angular like Kite.
- Neutral charcoal palette: #1a1a1a, #252525, #2a2a2a. NO blue/navy tint.
- Font: Lato via Google Fonts CDN.
- Backend code is at `/Users/proxy/trading/lite/backend/` — DO NOT modify.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/pages/Dashboard.tsx` | **Rewrite** | Full-height chart + left options panel layout |
| `src/components/OptionsPanel.tsx` | **Create** | New left-side options panel container (collapsed/expanded/hidden states) |
| `src/components/OptionsChainCollapsed.tsx` | **Create** | Compact view: CE LTP | Strike | PE LTP |
| `src/components/OptionsChainExpanded.tsx` | **Create** | Full view: OI + IV + LTP | Strike | LTP + IV + OI |
| `src/components/ExpiryTabs.tsx` | **Create** | Horizontal scrollable expiry pills |
| `src/components/ChainFilterTabs.tsx` | **Create** | ITM / ATM / OTM / Full filter bar |
| `src/components/NiftyChart.tsx` | **Modify** | Accept optional `symbol` prop for option chart overlay |
| `src/components/OptionsChain.tsx` | **Delete** | Replaced by OptionsPanel + collapsed/expanded views |
| `src/components/OptionsSidebarPanel.tsx` | **Delete** | Replaced by OptionsPanel |
| `src/components/OrderTicket.tsx` | **Keep** | Still used on mobile |
| `src/components/OrderModal.tsx` | **Keep** | Triggered by B/S buttons |
| `src/store/useStore.ts` | **Modify** | Add `chainView`, `chainFilter`, `optionChartSymbol` state |
| `src/components/Sidebar.tsx` | **Modify** | Remove options chain toggle button (panel is always visible) |
| `src/components/App.tsx` | **Modify** | Remove OptionsSidebarPanel import/mount |

---

## Task 1: Add new store state for panel controls

**Files:**
- Modify: `frontend/src/store/useStore.ts`

- [ ] Add new state fields and actions to the store interface and implementation:

```typescript
// Add to AppState interface (after line 43):
chainView: 'collapsed' | 'expanded'
chainFilter: 'ALL' | 'ITM' | 'ATM' | 'OTM'
chainPanelOpen: boolean
optionChartSymbol: string | null  // security_id for option chart, null = show NIFTY

// Add actions:
setChainView: (view: AppState['chainView']) => void
setChainFilter: (filter: AppState['chainFilter']) => void
setChainPanelOpen: (open: boolean) => void
setOptionChartSymbol: (symbol: string | null) => void
```

```typescript
// Add to create() defaults (after line 92):
chainView: 'collapsed',
chainFilter: 'ALL',
chainPanelOpen: true,
optionChartSymbol: null,

// Add action implementations:
setChainView: (chainView) => set({ chainView }),
setChainFilter: (chainFilter) => set({ chainFilter }),
setChainPanelOpen: (chainPanelOpen) => set({ chainPanelOpen }),
setOptionChartSymbol: (optionChartSymbol) => set({ optionChartSymbol }),
```

- [ ] Remove `optionsSidebarOpen` and `toggleOptionsSidebar` from both the interface and implementation (replaced by `chainPanelOpen`).

- [ ] Commit: `feat: add chain panel state (view, filter, panel toggle, option chart symbol)`

---

## Task 2: Create ExpiryTabs component

**Files:**
- Create: `frontend/src/components/ExpiryTabs.tsx`

- [ ] Create horizontal scrollable expiry pills. Show only the first 5 weekly expiries as compact tabs (e.g. "10 Mar", "17 Mar"). Active expiry highlighted with brand color. Clicking a tab calls `setSelectedExpiry()` which triggers a chain reload in App.tsx.

```tsx
import { useStore } from '../store/useStore'

function formatExpiry(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export default function ExpiryTabs() {
  const { snapshot, selectedExpiry, setSelectedExpiry } = useStore()
  const expiries = snapshot?.expiries?.slice(0, 5) ?? []
  const active = selectedExpiry ?? snapshot?.active_expiry ?? ''

  return (
    <div className="flex items-center gap-0.5 overflow-x-auto px-2 py-1">
      {expiries.map((exp) => (
        <button
          key={exp}
          onClick={() => setSelectedExpiry(exp)}
          className={`shrink-0 px-2 py-0.5 text-[11px] font-medium transition-colors rounded-sm ${
            exp === active
              ? 'bg-brand text-bg-primary'
              : 'text-text-muted hover:text-text-primary hover:bg-bg-hover'
          }`}
        >
          {formatExpiry(exp)}
        </button>
      ))}
    </div>
  )
}
```

- [ ] Commit: `feat: create ExpiryTabs horizontal pill component`

---

## Task 3: Create ChainFilterTabs component

**Files:**
- Create: `frontend/src/components/ChainFilterTabs.tsx`

- [ ] Create filter tabs for ITM/ATM/OTM/Full. These filter which strikes are shown. The filtering logic lives here — it exports the filter, and the chain views use the store value.

```tsx
import { useStore } from '../store/useStore'

const FILTERS = ['ALL', 'ITM', 'ATM', 'OTM'] as const

export default function ChainFilterTabs() {
  const { chainFilter, setChainFilter } = useStore()

  return (
    <div className="flex items-center gap-0.5 px-2 py-1">
      {FILTERS.map((f) => (
        <button
          key={f}
          onClick={() => setChainFilter(f)}
          className={`px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide transition-colors rounded-sm ${
            f === chainFilter
              ? 'bg-bg-hover text-text-primary'
              : 'text-text-muted hover:text-text-secondary'
          }`}
        >
          {f === 'ALL' ? 'Full' : f}
        </button>
      ))}
    </div>
  )
}
```

- [ ] Commit: `feat: create ChainFilterTabs (ITM/ATM/OTM/Full)`

---

## Task 4: Create OptionsChainCollapsed component

**Files:**
- Create: `frontend/src/components/OptionsChainCollapsed.tsx`

- [ ] Create the compact options chain view. Shows only: CE LTP | Strike | PE LTP. Each LTP cell has hover-reveal B/S buttons. Each row has a small chart icon button. ATM row highlighted. Clicking the LTP selects the quote.

The component receives filtered rows as a prop (filtering is done in the parent OptionsPanel).

```tsx
import { useEffect, useRef } from 'react'
import { LineChart } from 'lucide-react'

import { useStore } from '../store/useStore'
import type { OptionChainRow } from '../lib/api'

interface Props {
  rows: OptionChainRow[]
}

export default function OptionsChainCollapsed({ rows }: Props) {
  const { selectedQuote, setSelectedQuote, openOrderModal, setOptionChartSymbol } = useStore()
  const atmRef = useRef<HTMLTableRowElement>(null)

  useEffect(() => {
    if (atmRef.current) {
      atmRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [rows])

  const formatLTP = (ltp: number) => (ltp === 0 ? '--' : ltp.toFixed(2))

  return (
    <div className="flex-1 overflow-auto">
      <table className="w-full text-[12px] tabular-nums">
        <thead className="sticky top-0 z-10 bg-bg-secondary text-[10px] text-text-muted uppercase tracking-wide">
          <tr>
            <th className="py-[3px] px-1 text-right font-normal">LTP</th>
            <th className="py-[3px] px-1 text-center font-normal w-[70px]">Strike</th>
            <th className="py-[3px] px-1 text-left font-normal">LTP</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isATM = row.is_atm
            const activeCall = selectedQuote?.symbol === row.call.symbol
            const activePut = selectedQuote?.symbol === row.put.symbol

            return (
              <tr
                key={row.strike}
                ref={isATM ? atmRef : undefined}
                className={`group border-t border-border-secondary/40 h-[26px] transition-colors ${
                  isATM ? 'bg-[rgba(229,83,75,0.08)]' : 'hover:bg-bg-hover'
                }`}
              >
                {/* CE LTP + B/S */}
                <td
                  className={`group/ce relative cursor-pointer px-1 py-[2px] text-right font-medium text-profit ${
                    activeCall ? 'bg-profit/15' : ''
                  }`}
                  onClick={() => setSelectedQuote(row.call)}
                >
                  <span className="group-hover/ce:opacity-40">{formatLTP(row.call.ltp)}</span>
                  <div className="absolute inset-0 hidden group-hover/ce:flex items-center justify-center gap-0.5">
                    <button
                      onClick={(e) => { e.stopPropagation(); openOrderModal(row.call, 'BUY') }}
                      className="h-[18px] w-[18px] rounded-sm bg-btn-buy text-[9px] font-bold text-white"
                    >B</button>
                    <button
                      onClick={(e) => { e.stopPropagation(); openOrderModal(row.call, 'SELL') }}
                      className="h-[18px] w-[18px] rounded-sm bg-btn-sell text-[9px] font-bold text-white"
                    >S</button>
                  </div>
                </td>

                {/* Strike + chart button */}
                <td className="px-1 py-[2px] text-center">
                  <div className="flex items-center justify-center gap-0.5">
                    <button
                      onClick={() => setOptionChartSymbol(row.call.security_id ?? null)}
                      className="hidden group-hover:inline-flex h-[16px] w-[16px] items-center justify-center text-text-muted hover:text-text-primary"
                      title="View option chart"
                    >
                      <LineChart size={10} />
                    </button>
                    <span className={`font-medium ${isATM ? 'text-[#e53935]' : 'text-text-primary'}`}>
                      {row.strike}
                    </span>
                  </div>
                </td>

                {/* PE LTP + B/S */}
                <td
                  className={`group/pe relative cursor-pointer px-1 py-[2px] text-left font-medium text-loss ${
                    activePut ? 'bg-loss/15' : ''
                  }`}
                  onClick={() => setSelectedQuote(row.put)}
                >
                  <span className="group-hover/pe:opacity-40">{formatLTP(row.put.ltp)}</span>
                  <div className="absolute inset-0 hidden group-hover/pe:flex items-center justify-center gap-0.5">
                    <button
                      onClick={(e) => { e.stopPropagation(); openOrderModal(row.put, 'BUY') }}
                      className="h-[18px] w-[18px] rounded-sm bg-btn-buy text-[9px] font-bold text-white"
                    >B</button>
                    <button
                      onClick={(e) => { e.stopPropagation(); openOrderModal(row.put, 'SELL') }}
                      className="h-[18px] w-[18px] rounded-sm bg-btn-sell text-[9px] font-bold text-white"
                    >S</button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] Commit: `feat: create OptionsChainCollapsed (compact LTP/Strike/LTP view)`

---

## Task 5: Create OptionsChainExpanded component

**Files:**
- Create: `frontend/src/components/OptionsChainExpanded.tsx`

- [ ] Create the full options chain view. Shows: OI bar | IV% | LTP + B/S | Strike + chart | LTP + B/S | IV% | OI bar. OI visualized with background bars. Same B/S hover and chart button pattern as collapsed.

This is essentially the current `OptionsChain.tsx` table body, extracted to receive filtered rows as props.

```tsx
import { useEffect, useRef } from 'react'
import { LineChart } from 'lucide-react'

import { useStore } from '../store/useStore'
import type { OptionChainRow } from '../lib/api'

interface Props {
  rows: OptionChainRow[]
  maxOI: number
}

export default function OptionsChainExpanded({ rows, maxOI }: Props) {
  const { selectedQuote, setSelectedQuote, openOrderModal, setOptionChartSymbol } = useStore()
  const atmRef = useRef<HTMLTableRowElement>(null)

  useEffect(() => {
    if (atmRef.current) {
      atmRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [rows])

  const formatLTP = (ltp: number) => (ltp === 0 ? '--' : ltp.toFixed(2))
  const formatOI = (oi: number | null | undefined) => (oi == null ? '--' : oi.toFixed(1))

  return (
    <div className="flex-1 overflow-auto">
      <table className="w-full table-fixed text-[12px] tabular-nums">
        <thead className="sticky top-0 z-10 bg-bg-secondary text-[10px] text-text-muted uppercase tracking-wide">
          <tr>
            <th className="w-[16%] px-1 py-[3px] text-right font-normal">OI(L)</th>
            <th className="w-[11%] px-1 py-[3px] text-right font-normal">IV%</th>
            <th className="px-1 py-[3px] text-right font-normal">LTP</th>
            <th className="w-[60px] px-1 py-[3px] text-center font-normal">Strike</th>
            <th className="px-1 py-[3px] text-left font-normal">LTP</th>
            <th className="w-[11%] px-1 py-[3px] text-left font-normal">IV%</th>
            <th className="w-[16%] px-1 py-[3px] text-left font-normal">OI(L)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isATM = row.is_atm
            const activeCall = selectedQuote?.symbol === row.call.symbol
            const activePut = selectedQuote?.symbol === row.put.symbol
            const callOI = row.call.oi_lakhs ?? null
            const putOI = row.put.oi_lakhs ?? null
            const callOIPct = Math.min(40, callOI != null ? (callOI / maxOI) * 100 : 0)
            const putOIPct = Math.min(40, putOI != null ? (putOI / maxOI) * 100 : 0)

            return (
              <tr
                key={row.strike}
                ref={isATM ? atmRef : undefined}
                className={`group border-t border-border-secondary/40 h-[26px] transition-colors ${
                  isATM ? 'bg-[rgba(229,83,75,0.08)]' : 'hover:bg-bg-hover'
                }`}
              >
                {/* CE OI */}
                <td className="px-1 py-[2px] text-right">
                  <div className="relative overflow-hidden">
                    <div className="absolute inset-y-0 right-0 bg-profit/25" style={{ width: `${callOIPct}%` }} />
                    <span className="relative z-10">{formatOI(callOI)}</span>
                  </div>
                </td>
                {/* CE IV */}
                <td className="px-1 py-[2px] text-right text-text-muted">{row.call.iv?.toFixed(1) ?? '--'}</td>
                {/* CE LTP + B/S */}
                <td
                  className={`group/ce relative cursor-pointer px-1 py-[2px] text-right font-medium text-profit ${
                    activeCall ? 'bg-profit/15' : ''
                  }`}
                  onClick={() => setSelectedQuote(row.call)}
                >
                  <span className="group-hover/ce:opacity-40">{formatLTP(row.call.ltp)}</span>
                  <div className="absolute inset-0 hidden group-hover/ce:flex items-center justify-center gap-0.5">
                    <button onClick={(e) => { e.stopPropagation(); openOrderModal(row.call, 'BUY') }}
                      className="h-[18px] w-[18px] rounded-sm bg-btn-buy text-[9px] font-bold text-white">B</button>
                    <button onClick={(e) => { e.stopPropagation(); openOrderModal(row.call, 'SELL') }}
                      className="h-[18px] w-[18px] rounded-sm bg-btn-sell text-[9px] font-bold text-white">S</button>
                  </div>
                </td>
                {/* Strike + chart */}
                <td className="px-1 py-[2px] text-center">
                  <div className="flex items-center justify-center gap-0.5">
                    <button
                      onClick={() => setOptionChartSymbol(row.call.security_id ?? null)}
                      className="hidden group-hover:inline-flex h-[16px] w-[16px] items-center justify-center text-text-muted hover:text-text-primary"
                      title="View option chart"
                    >
                      <LineChart size={10} />
                    </button>
                    <span className={`font-medium ${isATM ? 'text-[#e53935]' : 'text-text-primary'}`}>{row.strike}</span>
                  </div>
                </td>
                {/* PE LTP + B/S */}
                <td
                  className={`group/pe relative cursor-pointer px-1 py-[2px] text-left font-medium text-loss ${
                    activePut ? 'bg-loss/15' : ''
                  }`}
                  onClick={() => setSelectedQuote(row.put)}
                >
                  <span className="group-hover/pe:opacity-40">{formatLTP(row.put.ltp)}</span>
                  <div className="absolute inset-0 hidden group-hover/pe:flex items-center justify-center gap-0.5">
                    <button onClick={(e) => { e.stopPropagation(); openOrderModal(row.put, 'BUY') }}
                      className="h-[18px] w-[18px] rounded-sm bg-btn-buy text-[9px] font-bold text-white">B</button>
                    <button onClick={(e) => { e.stopPropagation(); openOrderModal(row.put, 'SELL') }}
                      className="h-[18px] w-[18px] rounded-sm bg-btn-sell text-[9px] font-bold text-white">S</button>
                  </div>
                </td>
                {/* PE IV */}
                <td className="px-1 py-[2px] text-left text-text-muted">{row.put.iv?.toFixed(1) ?? '--'}</td>
                {/* PE OI */}
                <td className="px-1 py-[2px] text-left">
                  <div className="relative overflow-hidden">
                    <div className="absolute inset-y-0 left-0 bg-loss/25" style={{ width: `${putOIPct}%` }} />
                    <span className="relative z-10">{formatOI(putOI)}</span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] Commit: `feat: create OptionsChainExpanded (full OI/IV/LTP view)`

---

## Task 6: Create OptionsPanel container

**Files:**
- Create: `frontend/src/components/OptionsPanel.tsx`

- [ ] Create the left-side panel container that orchestrates everything: expiry tabs, filter tabs, collapsed/expanded toggle, the chain view, and a `>` collapse button. The panel sits directly right of the 40px nav sidebar.

Key behavior:
- **Panel width**: ~280px collapsed view, ~420px expanded view
- **Collapse button**: A `>` chevron on the right edge hides the panel entirely (only chevron visible as `<`)
- **View toggle**: Small buttons at top to switch collapsed/expanded
- **Filtering**: Uses `chainFilter` from store to filter rows before passing to child
- **ATM filter**: Shows ±3 strikes from ATM
- **ITM/OTM**: Based on whether strike is above/below ATM for calls/puts

```tsx
import { ChevronLeft, ChevronRight, Maximize2, Minimize2 } from 'lucide-react'

import { useStore } from '../store/useStore'
import ExpiryTabs from './ExpiryTabs'
import ChainFilterTabs from './ChainFilterTabs'
import OptionsChainCollapsed from './OptionsChainCollapsed'
import OptionsChainExpanded from './OptionsChainExpanded'

export default function OptionsPanel() {
  const {
    chain, snapshot,
    chainView, setChainView,
    chainFilter,
    chainPanelOpen, setChainPanelOpen,
  } = useStore()

  // Collapse toggle button (always visible)
  if (!chainPanelOpen) {
    return (
      <div className="hidden md:flex shrink-0 items-start">
        <button
          onClick={() => setChainPanelOpen(true)}
          className="mt-2 flex h-8 w-5 items-center justify-center border border-border-primary bg-bg-secondary text-text-muted hover:text-text-primary hover:bg-bg-hover transition-colors"
          title="Show options chain"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    )
  }

  const rows = chain?.rows ?? []
  const atm = rows.find((r) => r.is_atm)?.strike ?? 0

  // Filter rows based on chainFilter
  const filteredRows = rows.filter((row) => {
    if (chainFilter === 'ALL') return true
    if (chainFilter === 'ATM') return Math.abs(row.strike - atm) <= 150 // ±3 strikes at 50pt intervals
    if (chainFilter === 'ITM') return row.strike < atm // ITM calls are below ATM
    if (chainFilter === 'OTM') return row.strike > atm // OTM calls are above ATM
    return true
  })

  const maxOI = Math.max(
    ...rows.flatMap((r) => [r.call.oi_lakhs ?? 0, r.put.oi_lakhs ?? 0]),
    1,
  )

  const panelWidth = chainView === 'collapsed' ? 240 : 420
  const isExpanded = chainView === 'expanded'

  return (
    <div
      className="hidden md:flex shrink-0 flex-col border-r border-border-primary bg-bg-secondary overflow-hidden animate-fade-in"
      style={{ width: panelWidth }}
    >
      {/* Panel header */}
      <div className="flex items-center justify-between border-b border-border-primary px-2 py-1">
        <div className="flex items-center gap-1">
          <span className="text-[11px] font-medium text-text-secondary">Options</span>
          {snapshot && snapshot.spot > 0 && (
            <span className="text-[10px] tabular-nums text-text-muted">
              {snapshot.spot.toLocaleString('en-IN', { maximumFractionDigits: 1 })}
            </span>
          )}
        </div>
        <div className="flex items-center gap-0.5">
          {/* View toggle */}
          <button
            onClick={() => setChainView(isExpanded ? 'collapsed' : 'expanded')}
            className="flex h-5 w-5 items-center justify-center text-text-muted hover:text-text-primary transition-colors"
            title={isExpanded ? 'Compact view' : 'Detailed view'}
          >
            {isExpanded ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
          </button>
          {/* Collapse panel */}
          <button
            onClick={() => setChainPanelOpen(false)}
            className="flex h-5 w-5 items-center justify-center text-text-muted hover:text-text-primary transition-colors"
            title="Hide options chain"
          >
            <ChevronLeft size={14} />
          </button>
        </div>
      </div>

      {/* Expiry tabs */}
      <div className="border-b border-border-secondary">
        <ExpiryTabs />
      </div>

      {/* Filter tabs */}
      <div className="border-b border-border-secondary">
        <ChainFilterTabs />
      </div>

      {/* Chain content */}
      {!chain || !snapshot ? (
        <div className="flex flex-1 items-center justify-center text-xs text-text-muted">
          Waiting for data…
        </div>
      ) : filteredRows.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center text-text-muted">
          <p className="text-xs">No strikes match filter</p>
        </div>
      ) : isExpanded ? (
        <OptionsChainExpanded rows={filteredRows} maxOI={maxOI} />
      ) : (
        <OptionsChainCollapsed rows={filteredRows} />
      )}
    </div>
  )
}
```

- [ ] Commit: `feat: create OptionsPanel container with view/filter/collapse controls`

---

## Task 7: Rewrite Dashboard layout

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] Rewrite Dashboard to: full-height chart in main area, OptionsPanel on the left, no right sidebar. Keep mobile ticket button. Show degraded banner at top of chart area if needed.

```tsx
import { useState } from 'react'
import { Ticket, X } from 'lucide-react'

import NiftyChart from '../components/NiftyChart'
import OptionsPanel from '../components/OptionsPanel'
import OrderTicket from '../components/OrderTicket'
import { useStore } from '../store/useStore'

export default function Dashboard() {
  const { snapshot } = useStore()
  const [showMobileTicket, setShowMobileTicket] = useState(false)

  return (
    <div className="flex h-full">
      {/* Left: Options Panel */}
      <OptionsPanel />

      {/* Center: Full-height Chart */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {snapshot?.degraded && (
          <div className="border-b border-loss/30 bg-loss/10 px-3 py-1.5 text-xs text-loss">
            Market data degraded: {snapshot.degraded_reason ?? 'unknown'}
          </div>
        )}
        <div className="flex-1 min-h-0">
          <NiftyChart />
        </div>
      </div>

      {/* Mobile floating ticket button */}
      <button
        onClick={() => setShowMobileTicket(true)}
        className="fixed bottom-16 right-4 md:hidden z-20 h-12 w-12 rounded-full bg-signal text-white shadow-lg flex items-center justify-center"
      >
        <Ticket size={20} />
      </button>

      {/* Mobile order overlay */}
      {showMobileTicket && (
        <div className="fixed inset-0 z-40 md:hidden bg-black/60" onClick={() => setShowMobileTicket(false)}>
          <div
            className="absolute bottom-0 left-0 right-0 bg-bg-secondary rounded-t-lg p-4 max-h-[80vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-text-secondary">Order Ticket</span>
              <button onClick={() => setShowMobileTicket(false)} className="text-text-muted">
                <X size={16} />
              </button>
            </div>
            <OrderTicket />
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] Commit: `feat: rewrite Dashboard — full-height chart + left options panel`

---

## Task 8: Clean up App.tsx and Sidebar

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`

- [ ] In `App.tsx`: Remove `OptionsSidebarPanel` import and its mount inside ProtectedLayout.

- [ ] In `Sidebar.tsx`: Remove the options chain toggle button at the bottom (the Grid2x2 icon + `mt-auto` section). The OptionsPanel is now always part of the Dashboard and doesn't need a sidebar toggle.

- [ ] Delete the files that are no longer used:
  - `frontend/src/components/OptionsChain.tsx` — replaced by OptionsPanel + child views
  - `frontend/src/components/OptionsSidebarPanel.tsx` — replaced by OptionsPanel

- [ ] Commit: `refactor: remove old OptionsChain, OptionsSidebarPanel, sidebar toggle`

---

## Task 9: Fix expiry switching to actually reload chain data

**Files:**
- Modify: `frontend/src/App.tsx` (the chain loading useEffect, around line 210-235)

- [ ] The current `useEffect` for chain loading depends on `selectedExpiry`, so it should already re-fetch when expiry changes. Verify this works by checking the dependency array includes `selectedExpiry`. The current code at line 216:

```tsx
const chain = await fetchOptionChain(selectedExpiry ?? undefined)
```

This passes `selectedExpiry` to the API, so changing it should trigger a re-fetch. The dependency array at line 235 includes `selectedExpiry`. Confirm this works — if it doesn't, it may be because `setSelectedExpiry` in the ExpiryTabs doesn't trigger because the effect only runs when `selectedExpiry` changes but the chain data comes back with the same `active_expiry` and overwrites it.

Fix: In `setChain` (store line 105-109), do NOT overwrite `selectedExpiry` if it was manually set:

```typescript
setChain: (chain) => set((state) => ({
  chain,
  snapshot: chain?.snapshot ?? state.snapshot,
  // Only auto-set expiry if user hasn't manually selected one
  selectedExpiry: state.selectedExpiry ?? chain?.snapshot.active_expiry ?? null,
})),
```

Similarly in `applyChainEvent` (store line 126-136):

```typescript
applyChainEvent: (chain) => set((state) => {
  const nextSelected = state.selectedQuote
    ? chain.rows.flatMap((row) => [row.call, row.put]).find((quote) => quote.symbol === state.selectedQuote?.symbol) ?? state.selectedQuote
    : null
  return {
    chain,
    snapshot: chain.snapshot,
    // Don't overwrite manual expiry selection
    selectedExpiry: state.selectedExpiry ?? chain.snapshot.active_expiry ?? null,
    selectedQuote: nextSelected,
  }
}),
```

- [ ] Commit: `fix: preserve manual expiry selection when chain data refreshes`

---

## Task 10: Support option chart in NiftyChart

**Files:**
- Modify: `frontend/src/components/NiftyChart.tsx`

- [ ] Add support for viewing an individual option's chart. When `optionChartSymbol` is set in the store, show that option's chart instead of NIFTY. Add a small "× Back to NIFTY" button overlay when viewing an option chart.

The backend candle endpoint currently only supports NIFTY (security_id="13"). For option charts, we'd need to pass the security_id. Check if the backend's `_fetch_candles` method supports this. **If not**, this task should add a visual indicator showing which option is selected but explain that option-level candles require a backend change (which is out of scope per CLAUDE.md "DO NOT modify backend code").

For now, implement the UI toggle and show a placeholder message "Option chart for [symbol] — requires backend support" with a back button to return to NIFTY chart.

In the chart header area (the timeframe bar), add:

```tsx
// After the NIFTY 50 label, if optionChartSymbol is set:
{optionChartSymbol && (
  <div className="flex items-center gap-1 ml-2">
    <span className="text-[11px] text-brand">{optionChartSymbol}</span>
    <button
      onClick={() => setOptionChartSymbol(null)}
      className="text-[10px] text-text-muted hover:text-text-primary"
    >
      × NIFTY
    </button>
  </div>
)}
```

- [ ] Commit: `feat: add option chart placeholder with back-to-NIFTY toggle`

---

## Task 11: Build, verify, deploy

**Files:**
- No new files

- [ ] Run `cd frontend && npm run build` — must pass with ZERO errors.

- [ ] Fix any TypeScript or build errors.

- [ ] Deploy: `cd frontend && npx vercel --prod --yes`

- [ ] Verify the deployed site by navigating to https://litetrade.vercel.app and confirming:
  1. Chart is full-height
  2. Options chain panel is on the left
  3. Collapsed view shows LTP | Strike | LTP
  4. Expanded view shows full OI/IV/LTP columns
  5. `>` button collapses the panel, `<` reopens it
  6. Expiry tabs switch data
  7. ITM/ATM/OTM/Full filter works
  8. B/S buttons open OrderModal
  9. No right sidebar
  10. Mobile still works

- [ ] Commit: `chore: build verification and deployment`
