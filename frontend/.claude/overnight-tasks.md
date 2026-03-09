# Overnight Autonomous Redesign — Lite Options Terminal

You are redesigning the Lite Options Terminal frontend to be an **exact replica of Zerodha Kite's dark mode**. This is a React 19 + Vite 7 + Tailwind CSS v4 app. The backend is FastAPI on Railway.

## CRITICAL CSS RULE
Tailwind v4 uses `@layer`. NEVER put CSS rules outside `@layer base/components/utilities` in globals.css — unlayered CSS overrides all Tailwind utilities. The `@import "tailwindcss"` handles preflight/reset already.

## Architecture
- Frontend: `/Users/proxy/trading/lite/frontend/`
- Backend: `/Users/proxy/trading/lite/backend/` (DO NOT modify backend)
- Store: Zustand at `src/store/useStore.ts`
- API: `src/lib/api.ts` (all fetch functions)
- Styles: `src/styles/globals.css` (Tailwind v4 `@theme` block for design tokens)

## Deployment
- Build: `npm run build` (must pass with zero errors)
- Deploy: `cd /Users/proxy/trading/lite/frontend && npx vercel --prod --yes`
- Live URL: https://litetrade.vercel.app
- Backend: https://lite-options-api-production.up.railway.app
- Login: admin@lite.trade / admin123

## ZERODHA KITE DARK MODE — EXACT DESIGN SPEC

### Color Palette (MUST match exactly — NEUTRAL CHARCOAL, NOT navy/blue)
**CRITICAL: Kite dark mode is neutral dark gray. There is ZERO blue tint in backgrounds/borders. If you see any navy/blue-ish hex codes like #1b1b2f, #232341, #2d2d4a, #323253 — those are WRONG. Fix them immediately.**
```
Background primary:   #1a1a1a (very dark charcoal, almost black)
Background secondary: #252525 (slightly lighter gray)
Background tertiary:  #2a2a2a (inputs, search bars)
Background hover:     #2e2e2e (row hover)
Border primary:       #363636 (main dividers)
Border secondary:     #2e2e2e (subtle separators)
Text primary:         #e0e0e0 (near-white)
Text secondary:       #999999 (mid gray)
Text muted:           #666666 (dim labels)
Accent blue:          #2196f3 (Kite's blue for active nav/links)
Profit/green:         #4caf50
Loss/red:             #e53935
Orange accent:        #ff9800 (Kite uses orange for B button on hover)
```

**Also fix any hardcoded hex values in chart components (NiftyChart, Analytics) — no #1a1a2e, #2a2a44, #333350, #5e5e76. Use the neutral grays above.**

### Typography
- Font: `"Lato", system-ui, -apple-system, sans-serif` (Kite uses Lato)
- Add Google Fonts import for Lato (400, 500, 600, 700) in index.html
- Base size: 13px
- All numbers: `font-variant-numeric: tabular-nums`

### Header Bar (48px height, EXACTLY like Kite)
- Full width, dark background, bottom border
- LEFT section: Market indices with live prices
  - "NIFTY 50" label in muted text, then spot price in green/red, then change with % in green/red
  - Vertical divider (1px)
  - "SENSEX" with same pattern
  - VIX and PCR as small badges
- CENTER: Kite logo in RED #e74c3c (NOT blue — the kite logo is always red), then horizontal nav tabs
  - Tabs: Dashboard, Orders, Holdings (=Positions), Positions, Funds, Analytics
  - Active tab: blue text + blue bottom border (2px)
  - Inactive: gray text, blue on hover
  - NO rounded corners on tabs. Sharp, clean, minimal
- RIGHT section:
  - Green/red dot for WS connection status
  - Portfolio selector dropdown (minimal, no border visible)
  - User avatar circle (initials) + name
  - Logout icon

### Left Sidebar — Market Watch (300px wide, EXACTLY like Kite)
- Search bar at top with magnifying glass icon + "Search eg: 25500 CE" placeholder
  - Background: slightly lighter than sidebar (#2d2d4a)
  - Keyboard shortcut badge "⌘K" on right
- Below search: count label "Options (N)" + market status dot (green=OPEN)
- Scrollable list of option contracts:
  - Each row: symbol name (CE=green, PE=red) on left, LTP + bid×ask on right
  - Active/selected row: slightly highlighted background
  - On hover: show B (green) and S (red) mini buttons
  - Subtle bottom border between rows
  - 10px font for expiry date below symbol name

### Dashboard (main content area)
- Top: NIFTY 50 candlestick chart (280px height)
  - Timeframe selector: pill buttons (1m, 5m, 15m, 1h, D)
  - Active pill: blue background, white text
  - Chart uses lightweight-charts with Kite dark theme colors
- Below chart: Options Chain table
  - Sticky header row with light background (#232341)
  - Columns: CE Bid | CE LTP | CE Ask | CE IV | **STRIKE** | PE IV | PE Bid | PE LTP | PE Ask
  - ATM strike row: subtle blue highlight (bg-signal/8)
  - CE LTP cells: green text, clickable (cursor pointer, hover highlight)
  - PE LTP cells: red text, clickable
  - Expiry selector dropdown in header area
  - Spot price display next to expiry

### Right Panel (320px wide)
- Signal Panel: agent AI signal display with confidence, direction, entry/target/SL
- Market Depth card: bid/ask/IV/greeks grid
- Order Ticket:
  - Contract display (symbol, bid, ltp, ask)
  - BUY/SELL toggle (green/red, sharp not rounded)
  - Order type selector (MARKET/LIMIT/SL/SL-M)
  - Product selector (NRML/MIS)
  - Lots, Price, Trigger inputs
  - Summary: portfolio, signal, estimated value
  - Submit button (green for BUY, red for SELL)

### Login Page (Kite-style)
- Centered card on dark background
- Diamond logo in blue at top
- "Login to Lite" heading
- Email input with border, dark background
- Password input with border, dark background
- Blue "Login" button (full width, #387ed1)
- Footer: "Paper trading terminal — not connected to any live broker"
- NO pre-filled credentials, NO hints (security requirement)

### Orders Page
- Table: Time | Symbol | Side | Type | Qty | Price | Status
- Side column: green for BUY, red for SELL
- Status badges with appropriate colors
- Empty state: "No orders yet"

### Positions Page
- Table: Symbol | Net Qty | Avg | LTP | Unrealised | Margin | Exit button
- P&L colored (green positive, red negative)
- Exit button: red border, red text, hover red background
- Count in header: "Positions (N)"

### Holdings Page (= History/Tradebook)
- Table: Filled At | Symbol | Side | Qty | Avg Price | Charges
- Only shows filled orders

### Funds Page (Kite-style layout)
- "Hi, {name}" greeting
- Two-column layout:
  - LEFT: Equity section with large "Margin available" number, margins used, opening balance
  - RIGHT: P&L section with large realised P&L, unrealised, total equity
- Below: Fund breakdown grid cards

### Analytics Page
- Stat cards grid: Total Orders, Filled, Win Rate, Equity
- Equity curve chart (area chart, blue line)
- P&L by day horizontal bar chart
- Cards with rounded-sm corners, bg-secondary background

### Ticker Bar (bottom, 28px)
- Scrolling marquee of market indices
- NIFTY 50, VIX from live data + placeholder global indices
- CSS animation, pause on hover
- Seamless loop (duplicated items)

### Settings Page
- Environment info card
- Agent API key creation
- User invitation form
- Clean grid layout

### Global Design Rules
- NO rounded corners anywhere (sharp/angular like Kite) — exception: avatar circles, pills
- Border radius on inputs/buttons: 2px maximum (rounded-sm in Tailwind)
- All tables: no outer border, subtle row separators
- Hover states: subtle background change (#2a2a48)
- Focus states: blue border (border-signal)
- Transitions: 150ms ease on colors and opacity
- Loading spinner: blue ring, spinning
- Toast notifications: positioned bottom-right
- Scrollbars: thin (5px), matching dark theme

## WHAT TO FIX/IMPROVE

1. **globals.css**: Update @theme colors to match exact Kite palette above. Keep all custom CSS inside `@layer base`. Font to Lato.
2. **index.html**: Add Google Fonts link for Lato
3. **Header.tsx**: Must look exactly like Kite header — market data left, logo+nav center, user right
4. **MarketWatch.tsx**: Kite-style watchlist sidebar
5. **Dashboard.tsx**: Chart + options chain + right panel layout
6. **Login.tsx**: Clean card design matching Kite's login
7. **All pages**: Sharp corners (rounded-sm max), proper spacing, tabular numbers
8. **Analytics.tsx**: Fix any broken rendering, ensure charts work with empty data gracefully
9. **Toast.tsx**: Bottom-right positioned, auto-dismiss
10. **LoadingState.tsx**: Spinner should be blue, centered

## VERIFICATION AFTER EACH CHANGE
1. Run `npm run build` — must have ZERO errors
2. Deploy with `npx vercel --prod --yes`
3. Screenshot with `playwright screenshot --wait-for-timeout 3000 --viewport-size=1440,900 "https://litetrade.vercel.app" /tmp/verify.png`
4. View screenshot to verify visual correctness

## DO NOT
- Modify any backend code
- Change API endpoints or store logic (unless fixing a bug)
- Add new npm dependencies without good reason (Lato font via CDN is fine)
- Break TypeScript types
- Pre-fill login credentials
