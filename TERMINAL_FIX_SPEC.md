# NiftyDesk Lite — Terminal Fix Spec
**Date:** 2026-03-10  
**Goal:** Make the terminal look and work like a real broker terminal (Zerodha Kite-style) by EOD today.

## The Problem
The current terminal is incomplete and doesn't match the PLAN.md vision. Issues found:
1. **Options Chain missing OI columns** — The chain currently shows Bid/LTP/Ask/IV on both sides. PLAN requires OI (L) columns with bar visuals.
2. **No OI bar visualization** — No horizontal bars showing relative OI magnitude behind the numbers.
3. **ATM highlighting wrong** — ATM should have an orange background badge, not just an icon. bg-signal/8 is too subtle.
4. **MarketWatch sidebar (left)** shows option chain instruments in a search list — this is not a market watch, it's clutter. Should be removed or replaced with a simple watchlist of Nifty/Bank Nifty/VIX.
5. **Layout doesn't match PLAN** — Should be: fixed sidebar (48px icon-only nav, NOT the 300px MarketWatch) + chart + options chain + 320px right panel.
6. **No sidebar navigation** — Currently there's a horizontal nav in the header. PLAN requires left icon-only sidebar nav.
7. **SignalPanel is too small/hidden** — The signal box should be prominent at the top of the right panel showing direction, confidence, and instrument clearly.
8. **OrderTicket has SELL button** — PLAN is buy-only (CE or PE buy). Remove SELL. Show CE/PE toggle instead.
9. **Chart is only 280px** — Too small for a trading terminal. Should be ~40% of screen height.
10. **No position P&L progress bar** — Positions panel should show target/stop/current price as a visual progress bar.
11. **No live WebSocket indicator** — Header should show a green/red dot indicating WS connection status.
12. **TickerBar** — Should show live Nifty LTP ticking, VIX, PCR. Currently unclear if working.

## Target Layout (from PLAN.md)
```
┌─────────────────────────────────────────────────────────────┐
│ HEADER BAR (48px) — Logo | NIFTY LTP | SENSEX | VIX PCR | WS dot | Portfolio | Today P&L │
├────┬────────────────────────────────────────┬───────────────┤
│    │  MAIN AREA                             │ RIGHT PANEL   │
│    │  ┌──────────────────────────────────┐  │ (320px fixed) │
│ S  │  │  CHART (~40% height, 350-400px)  │  │               │
│ I  │  └──────────────────────────────────┘  │ Signal Box    │
│ D  │  ┌──────────────────────────────────┐  │ Depth Card    │
│ E  │  │  OPTIONS CHAIN (remaining height)│  │ Order Ticket  │
│    │  └──────────────────────────────────┘  │               │
│(48)│                                        │               │
└────┴────────────────────────────────────────┴───────────────┘
```

## Required Changes (priority order)

### P0 — Breaks the Kite-terminal feel
1. **Replace MarketWatch (300px sidebar) with a proper 48px icon-only left nav**
   - Icons: Dashboard, Positions, Orders, History, Funds, Analytics, Settings
   - Active state: accent line on left or highlighted icon
   - Tooltip on hover showing the label
   - Remove the `<MarketWatch />` component from the layout entirely

2. **Fix OptionsChain columns to match PLAN exactly:**
   ```
   OI(L) | IV% | LTP | STRIKE | LTP | IV% | OI(L)
   CE ←←←      center      →→→ PE
   ```
   - OI in lakhs (divide by 100000)
   - OI bar: `<div>` behind the OI number, width proportional to max OI in chain, green for CE, red for PE
   - ATM row: `background: rgba(255,107,53,0.15)` — make it visually clear

3. **Chart height: increase to 40% of available height** (use `flex-1` proportions or percentage)

4. **OrderTicket: CE/PE toggle instead of BUY/SELL**
   - Remove SELL button
   - Add CE | PE pill toggle (like PLAN spec)
   - The selected CE/PE from chain click should auto-set this
   - Keep order types (MARKET/LIMIT/etc)

### P1 — Important UX
5. **SignalPanel improvements:**
   - Signal direction badge should be visually large and clear (BIG red/green badge)
   - Confidence score shown as a number + small bar
   - "LOAD SIGNAL" button auto-fills the order ticket

6. **Header: add WS connection dot**
   - Green pulsing dot when `wsStatus === 'connected'`
   - Yellow dot when reconnecting
   - Red dot when disconnected

7. **Position cards (Positions page) — add P&L progress bar**
   - Visual bar: `stop price [====|=====] target price` with current LTP marker
   - Color: loss side red, profit side green

8. **NiftyChart: increase visibility**
   - Make timeframe buttons more visible (currently they may be small)
   - Add EMA 9 (white) and EMA 21 (blue) as default overlays
   - Ensure chart fills its container

### P2 — Polish
9. **TickerBar** — ensure it shows Nifty LTP, change, VIX, PCR and is live
10. **Header balance** — show virtual balance from selected portfolio clearly
11. **Loading states** — skeleton screens for chain and chart

## Technical Notes
- Frontend: React + Vite + Tailwind — `/Users/proxy/trading/lite/frontend/`
- CSS tokens already defined in `src/styles/globals.css` or tailwind config — check and use them
- Store: Zustand at `src/store/useStore.ts` — has `chain`, `snapshot`, `wsStatus`, `positions`, `latestSignal`, `selectedQuote`, `portfolios`
- The `setSelectedQuote(quote)` already works — clicking chain row sets it
- Backend is live on Railway, Dhan API integrated. Don't touch backend.
- Deploy: `cd frontend && vercel --prod` after changes

## Success Criteria
- [ ] Left sidebar is 48px icon-only (not 300px MarketWatch)
- [ ] Options chain shows OI(L) | IV% | LTP | Strike | LTP | IV% | OI(L) with OI bars
- [ ] ATM row has clear orange highlight
- [ ] Order ticket has CE/PE toggle, no SELL button
- [ ] Chart occupies ~40% height and has EMA overlays
- [ ] Header shows WS status dot
- [ ] Signal panel is prominent with large direction badge
- [ ] Site deploys clean to litetrade.vercel.app

## Files to modify
- `src/App.tsx` — layout structure, sidebar
- `src/components/MarketWatch.tsx` — replace with Sidebar component
- `src/components/Header.tsx` — add WS dot, cleanup
- `src/components/OptionsChain.tsx` — OI columns, ATM highlight, OI bars
- `src/components/OrderTicket.tsx` — CE/PE toggle, remove SELL
- `src/components/SignalPanel.tsx` — bigger, more prominent
- `src/pages/Dashboard.tsx` — chart height ratio
- `src/pages/Positions.tsx` — add P&L progress bar to position cards

## Deploy command
```bash
cd /Users/proxy/trading/lite/frontend && vercel --prod
```
