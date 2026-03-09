# Lite Options Terminal — Frontend

## Project
React 19 + Vite 7 + Tailwind CSS v4 trading terminal. Must look **exactly like Zerodha Kite dark mode**.

## CRITICAL: Color palette is NEUTRAL CHARCOAL, not navy
Kite dark mode has ZERO blue/navy tint. Backgrounds are pure dark grays (#1a1a1a, #252525, #2a2a2a). Borders are #363636, #2e2e2e. If you see ANY hex code with blue tint (like #1b1b2f, #232341, #2d2d4a, #323253, #5e5e76) in CSS or chart configs — it's WRONG. Replace with neutral grays.

## Critical Rules
- Tailwind v4: ALL custom CSS must be inside `@layer base`. Unlayered CSS overrides Tailwind utilities.
- Font: Lato via Google Fonts CDN (in index.html)
- NO rounded corners (use rounded-sm = 2px max). Sharp/angular like Kite.
- Kite logo is RED (#e74c3c), NOT blue. It's a kite shape, NOT a simple diamond.
- NO pre-filled login credentials. Security is critical.
- Analytics: AnalyticsPoint uses `label` and `value` fields (NOT date/timestamp/pnl).
- DO NOT modify backend code (in /Users/proxy/trading/lite/backend/)

## Build & Deploy
```bash
npm run build          # Must pass with ZERO errors
npx vercel --prod --yes  # Deploy to production
```

## Verify
```bash
playwright screenshot --wait-for-timeout 3000 --viewport-size=1440,900 "https://litetrade.vercel.app" /tmp/verify.png
```

## URLs
- Frontend: https://litetrade.vercel.app
- Backend: https://lite-options-api-production.up.railway.app
- Login: admin@lite.trade / admin123

## Design Spec
See `.claude/overnight-tasks.md` for the complete Zerodha Kite design specification.
