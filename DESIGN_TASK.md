# NiftyDesk Lite — Kite-Style Redesign Task

## Goal
Make the UI look and feel like Zerodha Kite as closely as possible. The current design has the right structure but wrong visual details. Fix everything below.

## Reference: What Kite looks like
- Dark background: `#1b1b1b` (header/sidebar), `#252525` (panels), `#1a1a1a` (body)
- Border color: `#2f2f2f` — very subtle
- Primary blue: `#387ed1` — used for active nav, links, signal color
- Text: `#ddd` primary, `#9a9a9a` secondary, `#666` muted
- Font: `"Lato"`, 12-13px for body, 11px for labels
- Profit/green: `#4bae4f` | Loss/red: `#e5534b`
- ATM highlight: subtle orange-red tint `rgba(235, 90, 70, 0.1)`
- Everything is COMPACT and DENSE — no wasted whitespace

## Specific issues to fix:

### 1. Header (Header.tsx)
- Left side: NIFTY and SENSEX values look fine — keep compact
- Center nav: active tab should have BLUE underline (`#387ed1`), not signal blue. Tab text should be `#ddd`, inactive `#9a9a9a`
- The kite logo SVG is wrong. Replace with text "kite" in the Kite font style or remove the logo, just keep nav tabs centered
- Right: WS dot fine, user avatar fine. Tighten up spacing.
- Header height should be 44px, not 48px (h-11 not h-12)

### 2. Sidebar (Sidebar.tsx)
- Currently icon-only with lucide icons. This is close to correct.
- Active state: blue left border `#387ed1`, blue icon `#387ed1`, bg `#252525`
- Hover: bg `#252525`, icon `#ddd`
- Inactive: icon `#666`
- Sidebar width: 40px (w-10), not 48px (w-12)

### 3. Options Chain (OptionsChain.tsx) — BIGGEST ISSUE
- The table needs to look EXACTLY like Kite:
  - CE side (left columns): OI bar fills from RIGHT to LEFT in GREEN, text right-aligned
  - PE side (right columns): OI bar fills from LEFT to RIGHT in RED, text left-aligned  
  - Strike column CENTER: bold, white, `#ddd` color — ATM strike highlighted with blue `#387ed1` bold
  - IV column: `#9a9a9a` muted text
  - LTP columns: GREEN for calls, RED for puts — click to select
  - Row height: 26px (very compact, py-0.5)
  - Table font: 12px tabular-nums
  - Header row: `#252525` bg, `#666` text, 11px, no bold
  - OI bar: max 40% width, opacity 0.25, positioned BEHIND text
  - ATM row: `rgba(235, 90, 70, 0.08)` background, ATM strike in orange-red `#e5534b`
  - Add a "Change" column for OI change if data available
  - Expiry selector: small, minimal border, dark bg
  - Spot price: right side, labeled clearly

### 4. SignalPanel (SignalPanel.tsx)
- Direction badge: BULLISH in green `#4bae4f`, BEARISH in red `#e5534b`, SIDEWAYS in `#9a9a9a`
- Make it more compact — remove excess padding
- Confidence bar: thinner (h-1 not h-1.5), blue `#387ed1` bar
- "Load Into Ticket" button: Kite blue `#387ed1`, not signal blue
- Font sizes: 11px for everything, 10px for labels

### 5. OrderTicket (OrderTicket.tsx)
- CE button: green `#4bae4f` when active, dim when inactive
- PE button: red `#e5534b` when active, dim when inactive
- BUY button: full-width, 30px height, green for CE, red for PE
- Input fields: `#252525` bg, `#2f2f2f` border, 12px text
- Labels: 10px `#666`
- Compact the whole thing — reduce all padding

### 6. DepthCard (Dashboard.tsx)
- Bid/Ask labels: `#9a9a9a`
- Values: `#ddd`
- Background: `#252525` cards
- Make rows horizontal: "Bid 100.50 | Ask 101.00" on one line, not grid

### 7. globals.css — Update color tokens
```css
--color-bg-primary: #1a1a1a;       /* main body */
--color-bg-secondary: #252525;     /* panels/cards */
--color-bg-tertiary: #2e2e2e;      /* inputs */
--color-bg-header: #1b1b1b;        /* header */
--color-border-primary: #2f2f2f;   /* main borders */
--color-border-secondary: #252525; /* subtle borders */
--color-text-primary: #dddddd;     /* primary text */
--color-text-secondary: #9a9a9a;   /* secondary */
--color-text-muted: #666666;       /* muted/labels */
--color-profit: #4bae4f;           /* green */
--color-loss: #e5534b;             /* red */
--color-signal: #387ed1;           /* kite blue — used EVERYWHERE for active/accent */
--color-atm: #e5534b;              /* ATM strike color */
```

### 8. General spacing
- Reduce ALL padding. Kite is DENSE.
- px-3 → px-2, py-2 → py-1, py-3 → py-2 everywhere
- Gap between elements: 8px max
- Section headers: 11px, `#666`, NO bold, uppercase

### 9. NiftyChart area
- Chart header: tight, 11px labels, `#666`
- Timeframe buttons (1m/5m/15m/1h/D): small, 24px wide, active = blue bg `#387ed1`, inactive = transparent
- Make sure chart fills the full allocated height

## Files to edit
- `/Users/proxy/trading/lite/frontend/src/styles/globals.css`
- `/Users/proxy/trading/lite/frontend/src/components/Header.tsx`
- `/Users/proxy/trading/lite/frontend/src/components/Sidebar.tsx`
- `/Users/proxy/trading/lite/frontend/src/components/OptionsChain.tsx`
- `/Users/proxy/trading/lite/frontend/src/components/SignalPanel.tsx`
- `/Users/proxy/trading/lite/frontend/src/components/OrderTicket.tsx`
- `/Users/proxy/trading/lite/frontend/src/components/NiftyChart.tsx`
- `/Users/proxy/trading/lite/frontend/src/pages/Dashboard.tsx` (DepthCard)

## Success criteria
- Screenshot the app at localhost after changes
- It should look unmistakably like Zerodha Kite dark theme
- Options chain table must be dense, professional, with OI bars behind text
- No excessive whitespace anywhere
- Blue accent `#387ed1` used consistently for active states
- Build must succeed: `cd /Users/proxy/trading/lite/frontend && npm run build`

## Workflow
1. Start with globals.css color tokens
2. Fix Header and Sidebar
3. Fix OptionsChain (most important)
4. Fix SignalPanel and OrderTicket
5. Fix Dashboard DepthCard
6. Build and verify
