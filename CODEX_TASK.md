# Codex Task: NiftyDesk Lite — Layout & Sidebar Fix

Working directory: /Users/proxy/trading/lite/frontend

Read TERMINAL_FIX_SPEC.md (one level up at /Users/proxy/trading/lite/TERMINAL_FIX_SPEC.md) for full context.

Your specific job (P0 items 1-3):

## Task 1: Replace MarketWatch with icon-only sidebar
Create a new component `src/components/Sidebar.tsx`:
- Fixed 48px wide, full height
- Icons only (use lucide-react icons that are already installed)
- Icons: LayoutDashboard (Dashboard /), List (Orders /orders), TrendingUp (Positions /positions), History (History /history), Wallet (Funds /funds), BarChart2 (Analytics /analytics), Settings (Settings /settings)
- Active: left accent border in signal color (`border-l-2 border-signal`)
- Tooltip on hover: use `title` attribute for simplicity
- CSS: bg-bg-primary, border-r border-border-primary

Update `src/App.tsx` ProtectedLayout:
- Remove `<MarketWatch />` 
- Add `<Sidebar />` in its place
- Main content area: `ml-12` (48px) since sidebar is fixed

## Task 2: Fix OptionsChain columns
Modify `src/components/OptionsChain.tsx`:

Change the table columns from:
`Bid | LTP | Ask | IV | Strike | IV | Bid | LTP | Ask`

To:
`OI(L) | IV% | LTP | Strike | LTP | IV% | OI(L)`

- OI(L) = oi_lakhs from the chain data (already in schema). If not present, show `--`
- Add OI bars: for each row, compute `oi / maxOI * 100` as a percentage for bar width
  - CE side: green bar behind the OI number (bg-profit/20, positioned absolute, right-aligned, in a relative container)
  - PE side: red bar behind the OI number (bg-loss/20, positioned absolute, left-aligned)
  - maxOI = max(all row call oi_lakhs, all row put oi_lakhs) in the chain
- ATM row: use className `bg-[rgba(255,107,53,0.12)]` instead of bg-signal/8
- Column widths: `w-[15%] w-[12%] w-[12%] w-[14%] w-[12%] w-[12%] w-[15%]`
- Keep click behavior on LTP cells (setSelectedQuote)

## Task 3: Chart height
In `src/pages/Dashboard.tsx`:
Change the chart container from `h-[280px]` to `h-[42%]` (percentage of flex parent height).
The options chain container below should get `flex-1 overflow-auto` (already has it, just confirm).

After all changes: run `npm run build` to verify no TS errors.
DO NOT run vercel deploy — claude code will handle that.
