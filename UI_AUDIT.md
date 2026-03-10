# Lite Options Terminal — UI Audit & Redesign Plan

**Date:** 2026-03-11
**Branch:** `ui-audit`
**Reference:** Zerodha Kite web (dark mode) — the gold standard for Indian trading terminals

---

## Part 1: Audit Findings

### A. CRITICAL BUGS (Functional)

| # | Issue | Severity |
|---|-------|----------|
| 1 | **Portfolio ID hardcoded to `"manual"` in Zustand store** — `selectedPortfolioId` defaults to `'manual'` but new signup creates `manual-{uuid}`. Every API call (orders, positions, funds, analytics) 404s until portfolios load and override it. Race condition on first load causes error toasts. | P0 |
| 2 | **Funds page shows spinner forever on mobile** — same root cause as #1; funds API returns 404, loading state never resolves. | P0 |
| 3 | **Login page lost signup form** — linter/external edit reverted Login.tsx to login-only with "Accounts are provisioned by an administrator" text. But the deployed Vercel version still has signup. Local code and deployed code are out of sync. | P1 |
| 4 | **Console errors on every page load** — 10+ `Failed to load resource` errors from the portfolio_id=manual 404s. Visible to anyone opening devtools. | P1 |

### B. IDENTITY & BRANDING

| # | Issue | Kite Reference |
|---|-------|----------------|
| 5 | **No real logo** — "lite" is plain text with `tracking-[0.3em]`. Kite has a distinctive red kite shape that's instantly recognizable. Lite needs a proper logo/mark. | Kite has a red angular kite shape SVG |
| 6 | **Favicon is a blue rounded square with diamond** — generic, looks like any SaaS app. Not the same as the "lite" brand. Should match the app's logo. | Kite favicon matches their logo exactly |
| 7 | **No apple-touch-icon, no manifest.json** — mobile "Add to Home Screen" shows a blank icon. No PWA support. | Kite has full PWA manifest |
| 8 | **Page title is "Lite Options"** — should update dynamically per page (e.g., "Orders — Lite", "NIFTY 24,500 — Lite") | Kite shows spot price in title |

### C. LOGIN PAGE

| # | Issue | Kite Reference |
|---|-------|----------------|
| 9 | **Dark login on dark background** — the login card barely stands out. No visual hierarchy. | Kite login is white card on light gray — maximum contrast. Clean, confident. |
| 10 | **Input fields blend into the card** — same dark gray for both input bg and card bg. Borders are too subtle. | Kite uses outlined inputs with floating labels, clear visual separation |
| 11 | **Login button is muted blue** — doesn't command attention. Uses `bg-signal` which is a muted `#387ed1`. | Kite's login button is bold `#e74c3c` red — their brand color |
| 12 | **No password visibility toggle** | Kite has an eye icon toggle |
| 13 | **No "forgot password" flow** | Kite has "Forgot user ID or password?" link |

### D. HEADER BAR

| # | Issue | Kite Reference |
|---|-------|----------------|
| 14 | **NIFTY 50 shows "0.00"** when market is closed — should show last known price. "0.00 +0.00 (0.00%)" looks broken, not graceful. | Kite shows the last closing price with proper formatting |
| 15 | **Navigation tabs lack active indicator weight** — the active tab has a thin underline but the text weight doesn't change. Hard to tell which page you're on at a glance. | Kite uses a clear blue bottom border (3px) + slightly bolder text |
| 16 | **"Holdings" tab exists but there's no Holdings page** — it navigates to nothing. This is for equities, which lite doesn't support. | Remove it |
| 17 | **Portfolio dropdown says "Audit User's Portfolio"** — too long, truncates. Should show portfolio kind ("Manual" / "Agent"). | Kite doesn't have this but the equivalent should be compact |
| 18 | **User avatar is a plain letter in a circle** — no logout confirmation. Clicking logout is instant, no "are you sure?" | Kite has a proper dropdown with profile, settings, logout |
| 19 | **WebSocket status dot ("connected") is always visible** — takes up header space for info the user doesn't need. Should only show when disconnected. | Kite hides connection status unless there's an issue |

### E. SIDEBAR

| # | Issue | Kite Reference |
|---|-------|----------------|
| 20 | **Icon-only sidebar at 40px is good** — matches Kite's approach. But icons have no tooltips. User has to guess what each icon means. | Kite sidebar icons show labels on hover |
| 21 | **Active sidebar icon highlight is too subtle** — a thin left border in blue. Easy to miss. | Should be more prominent — background highlight or bold icon color |
| 22 | **Settings icon in sidebar goes to /settings page** — but Settings page exists and is basically empty/placeholder. | Either build it or remove the icon |

### F. DASHBOARD LAYOUT

| # | Issue | Kite Reference |
|---|-------|----------------|
| 23 | **Chart takes 42% of height** — good, but the TradingView watermark is oversized and distracting when chart is empty. | Kite uses their own chart library, no third-party watermark |
| 24 | **Options Chain header says "Options Chain NIFTY weekly contracts"** — the label and description are jammed together with no visual separation. | Should be structured: title on left, expiry selector on right |
| 25 | **Options Chain is empty** — columns show but no data rows. When market is closed / data unavailable, should show last known data or a clear "Market closed" state. | Kite shows the last available option chain data |
| 26 | **Right panel (300px) has too many sections crammed** — Signal panel + Market Depth + Order Ticket all stacked. Signal panel dominates with a large green "BULLISH" bar. | This needs to be reimagined — signal should be subtle, order ticket should be primary |
| 27 | **Order Ticket has CE/PE toggle buttons that are too large** — green CE button takes up full width. Toggle should be compact. | Kite's order window is a modal, clean and focused |
| 28 | **"BUY CE" button is disabled with no clear reason why** | Should show a hint: "Select a contract" |
| 29 | **"Portfolio: manual" and "Signal: None"** displayed in order ticket — meaningless to the user. | Remove or make contextual |

### G. TICKER BAR (Bottom)

| # | Issue | Kite Reference |
|---|-------|----------------|
| 30 | **Scrolling ticker with NIFTY, S&P 500, NASDAQ, DOW 30, Bitcoin, Ethereum, Gold, Crude Oil** — none of these (except NIFTY) have data. All show "--". | Either fetch real data for these or remove them. A ticker of dashes is worse than no ticker. |
| 31 | **Ticker duplicates items** — the same 8 items repeat in a loop, visible simultaneously. Looks like a bug. | If using a marquee, ensure only one set is visible at a time |
| 32 | **Takes up ~28px at the bottom** — screen real estate wasted on non-functional data. | Only show if data is available |

### H. ORDERS / POSITIONS / HISTORY PAGES

| # | Issue | Kite Reference |
|---|-------|----------------|
| 33 | **"No orders yet" is plain text in a table cell** — no illustration, no call to action. | Kite shows illustrations for empty states with guidance text |
| 34 | **Table headers are ALL CAPS but inconsistent** — Orders page has Title Case ("Time", "Symbol") while Funds page uses ALL CAPS ("CASH BALANCE"). | Pick one convention and stick to it |
| 35 | **No search or filter** — as orders accumulate, there's no way to find specific ones. | Kite has search/filter on all table views |
| 36 | **Column widths are even-distributed** — "Side" and "Type" columns get the same width as "Symbol", wasting space. | Columns should be sized by content |

### I. FUNDS PAGE

| # | Issue | Kite Reference |
|---|-------|----------------|
| 37 | **Equity and P&L sections are reasonable** — the Kite-style split (Equity left, P&L right) is a good pattern. | Matches Kite well |
| 38 | **Fund Breakdown grid cards are too large** — 3-column grid of oversized cards for 7 simple key-value pairs. A compact list would be better. | Kite uses a simple 2-column table for this |
| 39 | **Values show "0" not "₹0" or "₹0.00"** — no currency symbol anywhere in the app. | All monetary values should have ₹ prefix |

### J. ANALYTICS PAGE

| # | Issue | Kite Reference |
|---|-------|----------------|
| 40 | **Stats cards (Total Orders, Filled, Win Rate, Equity) are good** — clear layout. | OK |
| 41 | **Equity Curve shows "No equity data yet"** — large empty gray box. Needs a better empty state. | Show a flat line at starting balance or an illustration |
| 42 | **P&L by Day shows a tiny green square for today's ₹0** — the bar chart is rendering a dot. Minimum bar width needed. | Minimum visible bar width |

### K. MOBILE EXPERIENCE

| # | Issue | Kite Reference |
|---|-------|----------------|
| 43 | **Header is too cramped at 390px** — "NIFTY 50 0.00 +0.00" + portfolio dropdown + avatar + logout all crammed into one row. Text wraps. | Kite mobile app has a separate simplified header |
| 44 | **Chart + Options Chain are stacked but chain only shows LTP/Strike/LTP** — OI and IV columns hidden. Makes sense for space but the 3 columns look sparse. | Consider a card-based chain view for mobile |
| 45 | **Mobile bottom nav is good** — 5 icons (Dashboard, Orders, Positions, Funds, Analytics). Matches Kite's mobile tab bar pattern. | Good |
| 46 | **Floating order ticket button (blue circle)** — good idea, opens a bottom sheet. But the bottom sheet has SignalPanel + OrderTicket stacked, making it very long to scroll. | Simplify mobile order sheet — just the essential fields |
| 47 | **No pull-to-refresh** — users expect this on mobile for data refresh. | Add pull-to-refresh gesture |
| 48 | **Ticker bar still shows on mobile** — takes precious vertical space with no useful data. | Hide on mobile |

### L. TYPOGRAPHY & COLOR

| # | Issue | Kite Reference |
|---|-------|----------------|
| 49 | **Lato font is a solid choice** — clean, readable at small sizes. Matches Kite. | Kite uses their own variant but Lato is close |
| 50 | **12px base font is correct for terminal density** | Matches Kite |
| 51 | **Color palette is correctly neutral charcoal** — `#1a1a1a` primary, `#252525` secondary. No navy tint. | Correct |
| 52 | **Green (#4bae4f) and Red (#e5534b) are slightly muted** — Kite's green is brighter. Red is similar. | Consider brightening green to #00b386 (Kite's exact green) |
| 53 | **Signal blue (#387ed1) is used for too many things** — login button, active states, brand accent, links. Needs more purpose-driven color use. | Kite uses blue sparingly — mainly for links and active nav |

### M. ANIMATIONS & MICRO-INTERACTIONS

| # | Issue | Kite Reference |
|---|-------|----------------|
| 54 | **Zero animations** — pages switch instantly, no transitions. Toasts appear/disappear abruptly. | Kite has subtle slide/fade transitions |
| 55 | **No hover states on table rows** — options chain rows, order rows have no visual feedback. | Kite rows highlight on hover with a subtle bg change |
| 56 | **No loading skeletons** — data areas are empty white space until data arrives. | Kite uses skeleton/shimmer loaders |

---

## Part 2: Redesign Plan

### Phase 1: Fix Critical Bugs (must-do before any UI work)

1. **Fix portfolio ID initialization** — default `selectedPortfolioId` to empty string, wait for portfolios to load before making any portfolio-scoped API calls
2. **Sync Login.tsx** — restore signup/login toggle that was reverted
3. **Remove "Holdings" tab** — lite is options-only
4. **Fix ticker bar** — hide on mobile, only show items with data, or remove entirely

### Phase 2: Brand Identity

5. **Design a proper logo** — a minimal, angular "L" mark that evokes a kite/trading motif. Red (#e74c3c) like Kite's brand color.
6. **New favicon** — SVG matching the logo, red on transparent
7. **Add apple-touch-icon + manifest.json** — PWA-ready
8. **Dynamic page titles** — show spot price + page name

### Phase 3: Login Page Redesign

9. **White/light login card** on dark background (Kite style) — or a clean dark card with much higher contrast inputs
10. **Proper logo placement** at top of login card
11. **Floating label inputs** with clear borders
12. **Red brand-color CTA button**
13. **Password visibility toggle**
14. **Signup/Login toggle** with smooth transition

### Phase 4: Layout & Navigation

15. **Header cleanup** — show last known price (not 0.00), hide WS status unless disconnected, compact portfolio selector
16. **Sidebar tooltips** on hover
17. **Remove Settings from sidebar** (or build a real Settings page)
18. **Better active state indicators** — sidebar + header tabs

### Phase 5: Dashboard Overhaul

19. **Options Chain empty state** — show "Market closed" with last trading date, not empty table
20. **Right panel reorganization** — Order Ticket primary, Signal as a subtle banner, Depth collapsed by default
21. **Compact CE/PE toggle** — pill-style, not full-width buttons
22. **Better disabled states** — "Select a contract from the chain" with subtle arrow pointing left

### Phase 6: Data Tables & Empty States

23. **Consistent table styling** — fixed column widths, hover states, alternating row shading
24. **Empty state illustrations** — simple SVG illustrations for "No orders", "No positions", "No history"
25. **Currency formatting** — ₹ prefix on all monetary values
26. **Compact Funds page** — table layout instead of card grid

### Phase 7: Mobile Polish

27. **Simplified mobile header** — just spot price + hamburger or minimal nav
28. **Hide ticker bar on mobile**
29. **Streamlined mobile order sheet** — essential fields only
30. **Card-based option chain rows** for touch targets

### Phase 8: Animations & Polish

31. **Page transition fade** (100ms)
32. **Toast slide-in/out** animations
33. **Table row hover** states
34. **Loading skeleton** components
35. **Smooth portfolio switch** transition

---

## Design Principles (from studying Kite)

1. **Information density without clutter** — Kite shows MORE data in LESS space by using tight spacing, small fonts, and clear hierarchy
2. **Neutral when idle, vivid when active** — most of the UI is gray; color only appears for prices, P&L, and actions
3. **Empty states are graceful** — never show broken-looking zeros or empty tables without context
4. **Mobile is a first-class citizen** — not a shrunken desktop, but a reimagined layout
5. **Brand is subtle but present** — the red kite logo appears once; the rest is pure utility
