# Dashboard Improvements Plan

## Context
User feedback on the deployed dashboard. Five areas: test credentials, options panel polish, real-time chart, TradingView Advanced Chart, and option chart switching.

## Tasks

### Task 1: Test Credentials Management
Create a single test account and store credentials securely for Playwright testing. Delete any stray test accounts.
- Create a `.env.test` file (gitignored) with `TEST_EMAIL` and `TEST_PASSWORD`
- Verify `.gitignore` excludes `.env.test`
- Use these creds consistently in any future Playwright tests

### Task 2: Options Chain Collapsed View — OI Bars + Spacing Polish
Redesign `OptionsChainCollapsed.tsx` per the approved mockup (B-style):
- Add 3px horizontal OI bars below each row
  - CE OI: grows right-to-left, `rgba(229,83,75,0.25)` (red = resistance)
  - PE OI: grows left-to-right, `rgba(76,175,80,0.25)` (green = support)
  - Bar width proportional to `oi_lakhs / maxOI`
- Fix column headers: change "LTP / Strike / LTP" to "CE / Strike / PE" with more padding between them (not cramped)
- ATM row: left border accent `2px solid rgba(229,83,75,0.4)` + subtle bg tint + brighter text + bold
- LTP text: `#b0b0b0` for regular rows, `#e0e0e0` + font-weight-500 for ATM
- Strike text: `#666` at 10px, ATM strike in `#e53935` bold 700
- Remove green/red coloring from LTP text (use neutral `#b0b0b0`) — color is reserved for OI bars
- `tabular-nums` on all number columns
- Row height stays 24px + 3px bar + 1px gap = ~28px total
- Need `maxOI` prop (already computed in OptionsPanel)

### Task 3: Options Chain Expanded View — OI Columns + Hierarchy Polish
Redesign `OptionsChainExpanded.tsx` per the approved mockup (C-style):
- OI columns: 44px on each edge, bar fill behind text
  - CE OI bar fills right-to-left, `rgba(229,83,75,0.15)` (red)
  - PE OI bar fills left-to-right, `rgba(76,175,80,0.15)` (green)
  - Show OI value as `NNL` (e.g. "42L") at 9px, color `#555`
- IV columns: 38px, 9px text, color `#555`
- LTP: 11px, `#b0b0b0` regular, `#e0e0e0` + 600 weight for ATM
- Strike: 10px, `#666`, ATM in `#e53935` bold 700
- Column headers: 8px uppercase, `#555`, `letter-spacing: 0.4px`
- Same ATM left border accent as collapsed
- Row separators: 1px `#222` borders
- Row height: 26px (ATM: 28px)
- Swap green/red OI bar colors vs current (CE = red/resistance, PE = green/support)

### Task 4: OptionsPanel Prop Plumbing
Update `OptionsPanel.tsx` to pass `maxOI` to collapsed view (currently only passed to expanded).

### Task 5: Replace lightweight-charts with TradingView Advanced Chart Widget
Replace the custom `NiftyChart.tsx` (lightweight-charts) with TradingView's embeddable Advanced Chart widget:
- Use the TradingView Advanced Chart widget (`https://s3.tradingview.com/tv.js`)
- This provides out-of-the-box: real-time updates, drawing tools (fibonacci, trendlines, horizontal lines), indicators (MA, RSI, MACD, etc.), chart scaling, save/load studies
- Symbol: `NSE:NIFTY` for the index
- Theme: dark, matching our palette
- Features to enable: drawing toolbar, studies/indicators, volume
- Remove `lightweight-charts` dependency after migration
- Keep the timeframe bar above the chart or use TradingView's built-in interval selector
- Preserve alert functionality — TradingView widget has its own alert UX but we keep our backend alerts as price lines
- The widget handles real-time candle updates natively (solves the "current candle not updating" issue)
- Key: TradingView widget is an iframe-based embed — no direct API access to series data. Our alert price lines will use TradingView's `createStudy` or overlay mechanism if available, otherwise we display alerts in a sidebar panel instead of on-chart.

**Important considerations:**
- TradingView free embeds may have limitations (watermark, restricted symbols)
- NSE:NIFTY may or may not be available on the free widget — needs testing
- If NSE symbols don't work on free TradingView widget, fallback: keep lightweight-charts but add real-time candle updates via WebSocket snapshot data
- The `tv.js` widget needs a container div and configuration object

**Fallback (if TradingView widget doesn't support NSE:NIFTY):**
- Keep lightweight-charts
- Add real-time candle update: use WebSocket `market.snapshot` spot price to update the current (last) candle's close/high/low in real-time
- Add a `useEffect` that subscribes to snapshot changes and calls `series.update()` with the updated last candle

### Task 6: Option Chart Switching
When user clicks chart icon on an option row, change the chart to show that option's price data:
- Currently `setOptionChartSymbol` stores the `security_id` but NiftyChart doesn't use it
- Need: `fetchCandles` to accept an optional `symbol` param and pass it to backend
- Backend already supports symbol-based candle queries (check `/api/v1/market/candles` endpoint)
- If backend doesn't support option candles, show a toast "Option charts coming soon" and skip
- If using TradingView widget: change the widget symbol to the option's TradingView symbol (e.g. `NSE:NIFTY25MAR24000CE`) — may not be available on free widget

### Task 7: Build, Deploy, Verify
- `npm run build` — must pass with zero errors
- `npx vercel --prod --yes` — deploy
- Playwright screenshot to verify visual result

## Execution Order
1. Task 2 + Task 3 (parallel — independent components)
2. Task 4 (depends on Task 2)
3. Task 5 (chart replacement — biggest task)
4. Task 6 (depends on Task 5)
5. Task 1 (credentials — independent, do anytime)
6. Task 7 (final)
