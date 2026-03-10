# Lite Options Terminal — UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Lite Options Terminal from a broken, unusable prototype into a polished, Kite-quality dark trading terminal with green (#a3e635) brand identity, working TradingView charts, restructured UI components, and mobile-first responsiveness.

**Architecture:** React 19 + Vite 7 + Tailwind CSS v4 SPA with Zustand state management, WebSocket live data, and lightweight-charts for candlestick rendering. Backend is FastAPI on Railway (DO NOT modify). Frontend deploys to Vercel.

**Tech Stack:** React 19, TypeScript, Tailwind CSS v4 (@theme + @layer), Zustand, lightweight-charts, lucide-react, Vite 7

**Constraints:**
- DO NOT modify backend code (`/Users/proxy/trading/lite/backend/`)
- DO NOT add unnecessary npm dependencies
- All custom CSS must be inside `@layer base` (Tailwind v4 requirement)
- NO pre-filled login credentials anywhere
- Build must pass with ZERO errors before each deploy

**User Design Direction (overrides CLAUDE.md where conflicting):**
- Logo: Kite shape mirrored (pointing RIGHT), green #a3e635
- Primary brand color: green #a3e635
- Accent color: blue #387ed1
- Dark mode: keep neutral charcoal palette
- Fix: ALL broken TradingView components (charts, ticker)
- Fix: ALL poorly structured/stacked UI components

---

## File Structure

### New Files
| File | Purpose |
|------|---------|
| `src/components/Logo.tsx` | SVG kite logo component (green, pointing right) |
| `src/components/Skeleton.tsx` | Loading skeleton shimmer components |
| `public/logo.svg` | Standalone SVG logo for favicon/PWA |
| `public/apple-touch-icon.png` | 180x180 PWA icon |
| `public/manifest.json` | PWA manifest |

### Modified Files (by task)
| File | Changes |
|------|---------|
| `src/store/useStore.ts` | Fix portfolio ID default, add `portfoliosLoaded` flag |
| `src/styles/globals.css` | Update @theme colors (green primary), add animations, skeletons |
| `index.html` | Dynamic title support, manifest link, apple-touch-icon |
| `public/favicon.svg` | Replace with green kite logo |
| `src/pages/Login.tsx` | Full redesign with signup toggle, password visibility, green CTA |
| `src/components/Header.tsx` | Remove Holdings tab, hide WS when connected, compact portfolio, last-known price |
| `src/components/Sidebar.tsx` | Add tooltips, better active states, remove Settings |
| `src/pages/Dashboard.tsx` | Restructure right panel, extract DepthCard, mobile layout |
| `src/components/NiftyChart.tsx` | Fix chart colors, use CSS vars, handle empty/closed state |
| `src/components/OptionsChain.tsx` | Market closed state, better header layout, hover states |
| `src/components/OrderTicket.tsx` | Compact CE/PE toggle, disabled state hints, remove debug text |
| `src/components/SignalPanel.tsx` | Make subtle banner instead of dominating panel |
| `src/components/DepthCard.tsx` | Extract to own file, collapsed by default |
| `src/components/TickerBar.tsx` | Hide items with no data, hide on mobile, fix duplication |
| `src/components/MobileNav.tsx` | Green active state, match brand |
| `src/components/Toast.tsx` | Add slide-in/out animation |
| `src/components/LoadingState.tsx` | Add skeleton variant |
| `src/pages/Orders.tsx` | Empty state illustration, consistent headers, column sizing |
| `src/pages/Positions.tsx` | Same improvements as Orders |
| `src/pages/History.tsx` | Same improvements as Orders |
| `src/pages/Funds.tsx` | Currency formatting (₹), compact table layout |
| `src/pages/Analytics.tsx` | Better empty states, minimum bar widths |
| `src/pages/Settings.tsx` | Make functional or simplify |
| `src/App.tsx` | Gate API calls on portfoliosLoaded, page transition wrapper |
| `src/lib/api.ts` | No changes needed |

---

## Chunk 1: Critical Bug Fixes

### Task 1: Fix Portfolio ID Race Condition (P0)

**Files:**
- Modify: `src/store/useStore.ts:10-15` (default value)
- Modify: `src/App.tsx:50-90` (data fetching effects)

The root cause: `selectedPortfolioId` defaults to `'manual'` but signup creates `manual-{uuid}`. Every portfolio-scoped API call (orders, positions, funds, analytics) uses this ID and gets 404 until portfolios load.

- [ ] **Step 1: Fix store default**

In `src/store/useStore.ts`, change the `selectedPortfolioId` default from `'manual'` to `''` (empty string), and add a `portfoliosLoaded` boolean flag:

```typescript
// In the state interface, add:
portfoliosLoaded: boolean

// In create(), change:
selectedPortfolioId: '',
portfoliosLoaded: false,

// In setPortfolios, add:
setPortfolios: (ps) => {
  const current = get().selectedPortfolioId
  const manual = ps.find((p) => p.kind === 'manual') ?? ps[0]
  set({
    portfolios: ps,
    selectedPortfolioId: current && ps.some((p) => p.id === current) ? current : manual?.id ?? '',
    portfoliosLoaded: true,
  })
},
```

- [ ] **Step 2: Gate portfolio-scoped API calls in App.tsx**

In `src/App.tsx`, wrap the portfolio-scoped data fetching effect to only run when `portfoliosLoaded` is true and `selectedPortfolioId` is non-empty:

```typescript
// Change the portfolio data effect from:
useEffect(() => {
  if (!accessToken) return
  // ... fetch orders, positions, funds, analytics
}, [accessToken, selectedPortfolioId])

// To:
useEffect(() => {
  if (!accessToken || !portfoliosLoaded || !selectedPortfolioId) return
  // ... fetch orders, positions, funds, analytics
}, [accessToken, portfoliosLoaded, selectedPortfolioId])
```

Add `portfoliosLoaded` to the destructured store values at the top of `ProtectedLayout`.

- [ ] **Step 3: Verify build passes**

Run: `cd /Users/proxy/trading/lite/frontend && npm run build`
Expected: ZERO errors

- [ ] **Step 4: Commit**

```bash
git add src/store/useStore.ts src/App.tsx
git commit -m "fix: gate portfolio API calls until portfolios loaded — fixes 404 race condition"
```

---

### Task 2: Restore Signup Flow in Login Page

**Files:**
- Modify: `src/pages/Login.tsx` (add signup toggle)

The login page was reverted to login-only with "Accounts are provisioned by an administrator" text. The backend has a working `POST /auth/signup` endpoint. Restore the signup/login toggle.

- [ ] **Step 1: Add signup state and form**

Replace the entire `Login.tsx` with a login/signup toggle. Key changes:
- Add `mode` state: `'login' | 'signup'`
- Add `displayName` state for signup
- Toggle between login() and signup() API calls
- Replace "Accounts are provisioned" text with toggle link
- Keep paper trading disclaimer

```typescript
const [mode, setMode] = useState<'login' | 'signup'>('login')
const [displayName, setDisplayName] = useState('')

// In form onSubmit:
if (mode === 'signup') {
  await signup(email, displayName, password)
  addToast('success', 'Account created — signing in…')
  await login(email, password)
} else {
  await login(email, password)
  addToast('success', 'Signed in')
}

// Toggle link:
<button type="button" onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}>
  {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
</button>
```

- [ ] **Step 2: Verify signup API function exists in api.ts**

Check `src/lib/api.ts` for the `signup` export. It should already exist. If not, add:

```typescript
export async function signup(email: string, displayName: string, password: string) {
  return request('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, display_name: displayName, password }),
  })
}
```

- [ ] **Step 3: Build and verify**

Run: `cd /Users/proxy/trading/lite/frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add src/pages/Login.tsx src/lib/api.ts
git commit -m "fix: restore signup/login toggle on login page"
```

---

### Task 3: Remove Holdings Tab & Fix Header Data

**Files:**
- Modify: `src/components/Header.tsx`

- [ ] **Step 1: Remove "Holdings" from nav tabs**

In `Header.tsx`, find the tabs array and remove the Holdings entry. It navigates to nothing — lite is options-only.

- [ ] **Step 2: Show last known price instead of "0.00"**

When `snapshot?.spot_price` is 0 or undefined, show `'--'` instead of `'0.00 +0.00 (0.00%)'`. This prevents the broken-looking zeros when market is closed.

```typescript
const spotPrice = snapshot?.spot_price
const change = snapshot?.spot_change ?? 0
const changePct = snapshot?.spot_change_pct ?? 0
const hasData = spotPrice && spotPrice > 0

// Render:
{hasData ? (
  <>
    <span className={change >= 0 ? 'text-profit' : 'text-loss'}>
      {spotPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
    </span>
    <span className={`text-xs ${change >= 0 ? 'text-profit' : 'text-loss'}`}>
      {change >= 0 ? '+' : ''}{change.toFixed(2)} ({changePct.toFixed(2)}%)
    </span>
  </>
) : (
  <span className="text-text-muted">--</span>
)}
```

- [ ] **Step 3: Hide WebSocket status when connected**

Only show the WS status dot when `wsStatus !== 'connected'`. When connected, hide it entirely to save header space (Kite pattern).

- [ ] **Step 4: Build and commit**

```bash
npm run build
git add src/components/Header.tsx
git commit -m "fix: remove Holdings tab, handle zero prices, hide WS status when connected"
```

---

### Task 4: Fix Ticker Bar

**Files:**
- Modify: `src/components/TickerBar.tsx`

- [ ] **Step 1: Filter out items with no data**

Only render ticker items where the price is available (not 0, not undefined, not '--'). If no items have data, hide the entire ticker bar.

```typescript
const items = allItems.filter(item => item.price && item.price > 0)
if (items.length === 0) return null
```

- [ ] **Step 2: Hide on mobile**

Add `hidden md:flex` to the outer container so the ticker bar doesn't show on mobile viewports.

- [ ] **Step 3: Fix duplication visibility**

The marquee duplicates items for seamless scrolling, but both sets are visible simultaneously. Fix by ensuring the container has `overflow-hidden` and the animation width calculation is correct. The inner track should be `width: max-content` with only one set visible at a time.

- [ ] **Step 4: Build and commit**

```bash
npm run build
git add src/components/TickerBar.tsx
git commit -m "fix: ticker bar hides when no data, hidden on mobile, fix duplication"
```

---

## Chunk 2: Brand Identity & Theme

### Task 5: Create Green Kite Logo

**Files:**
- Create: `src/components/Logo.tsx`
- Create: `public/logo.svg`
- Replace: `public/favicon.svg`

- [ ] **Step 1: Design the SVG logo**

Create a kite shape pointing RIGHT (mirrored from Zerodha Kite which points left). The kite is an angular diamond shape with a tail, rendered in green #a3e635.

Create `src/components/Logo.tsx`:

```tsx
interface LogoProps {
  size?: number
  className?: string
}

export default function Logo({ size = 24, className = '' }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      className={className}
      aria-label="Lite"
    >
      {/* Kite shape pointing right — mirrored from Zerodha's left-pointing kite */}
      <path
        d="M8 32L28 12L56 32L28 52Z"
        fill="#a3e635"
      />
      <path
        d="M28 12L56 32L28 52"
        fill="#8bc926"
      />
      {/* Kite cross-spar */}
      <line x1="8" y1="32" x2="56" y2="32" stroke="#1a1a1a" strokeWidth="1.5" />
      <line x1="28" y1="12" x2="28" y2="52" stroke="#1a1a1a" strokeWidth="1.5" />
    </svg>
  )
}
```

- [ ] **Step 2: Create standalone SVG for favicon**

Write `public/favicon.svg` — same kite shape, green fill, transparent background, optimized for small sizes (remove cross-spar lines for clarity at 16px).

Write `public/logo.svg` — full version for PWA/touch icons.

- [ ] **Step 3: Build and commit**

```bash
npm run build
git add src/components/Logo.tsx public/favicon.svg public/logo.svg
git commit -m "feat: add green kite logo (mirrored, pointing right)"
```

---

### Task 6: Update Theme Colors

**Files:**
- Modify: `src/styles/globals.css`

- [ ] **Step 1: Update @theme block**

Update the Tailwind v4 `@theme` block to use the new brand colors while keeping the neutral charcoal palette:

```css
@theme {
  /* Brand */
  --color-brand: #a3e635;
  --color-brand-dark: #8bc926;
  --color-signal: #387ed1;

  /* Backgrounds — neutral charcoal (ZERO blue tint) */
  --color-bg-primary: #1a1a1a;
  --color-bg-secondary: #252525;
  --color-bg-tertiary: #2a2a2a;
  --color-bg-hover: #2e2e2e;

  /* Borders */
  --color-border-primary: #363636;
  --color-border-secondary: #2e2e2e;

  /* Text */
  --color-text-primary: #e0e0e0;
  --color-text-secondary: #999999;
  --color-text-muted: #666666;

  /* Semantic */
  --color-profit: #4caf50;
  --color-loss: #e53935;

  /* Charts */
  --color-candle-bull: #4caf50;
  --color-candle-bear: #e53935;
  --color-candle-bull-wick: #4caf50;
  --color-candle-bear-wick: #e53935;
}
```

- [ ] **Step 2: Add animation keyframes inside @layer base**

```css
@layer base {
  /* Page transitions */
  @keyframes fade-in {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Toast slide */
  @keyframes slide-in-right {
    from { opacity: 0; transform: translateX(100%); }
    to { opacity: 1; transform: translateX(0); }
  }

  @keyframes slide-out-right {
    from { opacity: 1; transform: translateX(0); }
    to { opacity: 0; transform: translateX(100%); }
  }

  /* Skeleton shimmer */
  @keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }

  .animate-fade-in {
    animation: fade-in 150ms ease-out;
  }

  .animate-slide-in {
    animation: slide-in-right 200ms ease-out;
  }

  .skeleton {
    background: linear-gradient(90deg, var(--color-bg-secondary) 25%, var(--color-bg-tertiary) 50%, var(--color-bg-secondary) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
  }
}
```

- [ ] **Step 3: Verify no hardcoded navy/blue hex codes remain**

Search the entire `src/` directory for any hex codes with blue tint: `#1a1a2e`, `#1b1b2f`, `#232341`, `#2a2a44`, `#2d2d4a`, `#323253`, `#333350`, `#5e5e76`. Replace all with their neutral charcoal equivalents from the palette above.

- [ ] **Step 4: Build and commit**

```bash
npm run build
git add src/styles/globals.css
git commit -m "feat: update theme with green brand color, add animations and skeleton"
```

---

### Task 7: PWA Manifest & Meta Tags

**Files:**
- Create: `public/manifest.json`
- Modify: `index.html`

- [ ] **Step 1: Create manifest.json**

```json
{
  "name": "Lite Options Terminal",
  "short_name": "Lite",
  "description": "Paper trading terminal for NIFTY options",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a1a",
  "theme_color": "#a3e635",
  "icons": [
    { "src": "/logo.svg", "sizes": "any", "type": "image/svg+xml" },
    { "src": "/apple-touch-icon.png", "sizes": "180x180", "type": "image/png" }
  ]
}
```

- [ ] **Step 2: Update index.html**

Add to `<head>`:
```html
<link rel="manifest" href="/manifest.json" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<meta name="theme-color" content="#a3e635" />
```

Update `<title>` to just "Lite" (dynamic titles will be set in React).

- [ ] **Step 3: Generate apple-touch-icon.png**

Create a 180x180 PNG from the logo SVG. This can be done by rendering the SVG to a canvas or using a simple green kite on dark background.

For now, a simple approach: create a minimal HTML that renders the SVG at 180x180 and screenshot it, or use the SVG directly (most modern iOS versions support SVG touch icons).

- [ ] **Step 4: Build and commit**

```bash
npm run build
git add public/manifest.json public/apple-touch-icon.png index.html
git commit -m "feat: add PWA manifest, apple-touch-icon, meta tags"
```

---

### Task 8: Dynamic Page Titles

**Files:**
- Modify: `src/App.tsx`

- [ ] **Step 1: Add useEffect for page title in each route**

Create a simple hook or use `useEffect` in `ProtectedLayout` to set `document.title` based on the current route:

```typescript
const location = useLocation()
const spotPrice = useStore(s => s.snapshot?.spot_price)

useEffect(() => {
  const titles: Record<string, string> = {
    '/': 'Dashboard',
    '/orders': 'Orders',
    '/positions': 'Positions',
    '/history': 'History',
    '/funds': 'Funds',
    '/analytics': 'Analytics',
    '/settings': 'Settings',
  }
  const page = titles[location.pathname] ?? 'Dashboard'
  const prefix = spotPrice && spotPrice > 0
    ? `${spotPrice.toLocaleString('en-IN')} — `
    : ''
  document.title = `${prefix}${page} — Lite`
}, [location.pathname, spotPrice])
```

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/App.tsx
git commit -m "feat: dynamic page titles with spot price"
```

---

## Chunk 3: Login Page Redesign

### Task 9: Complete Login Page Overhaul

**Files:**
- Modify: `src/pages/Login.tsx`

This combines: high-contrast card, logo placement, floating labels, green CTA, password visibility toggle, signup/login toggle (from Task 2).

- [ ] **Step 1: Rewrite Login.tsx**

Full rewrite of Login.tsx with:

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { login, signup } from '../lib/api'
import { useStore } from '../store/useStore'
import Logo from '../components/Logo'

export default function Login() {
  const navigate = useNavigate()
  const { addToast } = useStore()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (mode === 'signup') {
        await signup(email, displayName, password)
        await login(email, password)
        addToast('success', 'Account created')
      } else {
        await login(email, password)
        addToast('success', 'Signed in')
      }
      navigate('/')
    } catch (error) {
      addToast('error', error instanceof Error ? error.message : 'Failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-bg-primary">
      <div className="w-full mx-4 max-w-[380px] rounded-sm border border-border-primary bg-bg-secondary px-8 py-8">
        {/* Logo + Title */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <Logo size={40} />
          <div className="text-[20px] font-light tracking-[0.3em] text-text-primary">
            lite
          </div>
          <p className="text-[13px] text-text-muted">
            {mode === 'login' ? 'Sign in to your account' : 'Create your account'}
          </p>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          {/* Display name (signup only) */}
          {mode === 'signup' && (
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Display name"
              required
              className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-brand"
            />
          )}

          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            autoFocus
            required
            className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-brand"
          />

          {/* Password with visibility toggle */}
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              required
              className="w-full rounded-sm border border-border-primary bg-bg-primary px-3 py-2.5 pr-10 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-brand"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {/* Green brand CTA */}
          <button
            type="submit"
            disabled={loading || !email || !password || (mode === 'signup' && !displayName)}
            className="w-full rounded-sm bg-brand py-2.5 text-sm font-semibold text-bg-primary transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {loading
              ? (mode === 'login' ? 'Signing in…' : 'Creating account…')
              : (mode === 'login' ? 'Login' : 'Sign up')}
          </button>
        </form>

        {/* Toggle */}
        <p className="mt-5 text-center text-[12px] text-text-muted">
          <button
            type="button"
            onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
            className="text-signal hover:underline"
          >
            {mode === 'login'
              ? "Don't have an account? Sign up"
              : 'Already have an account? Sign in'}
          </button>
        </p>

        <p className="mt-4 text-center text-[11px] leading-4 text-text-muted">
          Paper trading terminal &mdash; not connected to any live broker
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify `signup` function exists in api.ts**

If `signup` is not exported from `src/lib/api.ts`, add it (see Task 2 Step 2).

- [ ] **Step 3: Build and commit**

```bash
npm run build
git add src/pages/Login.tsx
git commit -m "feat: redesign login page with signup toggle, password visibility, green CTA"
```

---

## Chunk 4: Header, Sidebar & Navigation

### Task 10: Header Redesign

**Files:**
- Modify: `src/components/Header.tsx`

Combine fixes from Task 3 with full visual overhaul.

- [ ] **Step 1: Rewrite Header.tsx**

Structure: Logo + "lite" text (left) | Nav tabs (center) | Market data + portfolio + user (right)

Key changes:
- Add `<Logo size={20} />` next to "lite" text
- Remove Holdings tab from nav
- Active tab: green bottom border (3px) + `text-text-primary` font weight
- Inactive tab: `text-text-muted`, `hover:text-text-secondary`
- Market data: show `'--'` when no data, green/red coloring when data available
- WS status: only show when NOT connected (show orange dot with "reconnecting…")
- Portfolio selector: show just the portfolio `kind` ("Manual" / "Agent"), not the full name
- User section: initials circle + compact logout

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/components/Header.tsx
git commit -m "feat: redesign header with logo, cleaner nav, conditional WS status"
```

---

### Task 11: Sidebar Improvements

**Files:**
- Modify: `src/components/Sidebar.tsx`

- [ ] **Step 1: Add tooltips and better active states**

Changes:
- Each icon gets a `title` attribute and a hover tooltip (CSS `group` + absolute positioned label)
- Active icon: green left border (3px) + green icon color + subtle bg-bg-tertiary background
- Remove Settings icon from sidebar (Settings page is a placeholder)
- Hover state: bg-bg-hover background on icon container

```tsx
// Tooltip pattern for each nav item:
<div className="group relative">
  <NavLink to={item.path} className={({ isActive }) =>
    `flex h-10 w-10 items-center justify-center border-l-[3px] transition-colors ${
      isActive
        ? 'border-brand text-brand bg-bg-tertiary'
        : 'border-transparent text-text-muted hover:text-text-secondary hover:bg-bg-hover'
    }`
  }>
    <item.icon size={18} />
  </NavLink>
  <div className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 rounded-sm bg-bg-tertiary px-2 py-1 text-xs text-text-primary opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
    {item.label}
  </div>
</div>
```

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/components/Sidebar.tsx
git commit -m "feat: sidebar tooltips, green active indicator, remove settings icon"
```

---

## Chunk 5: Dashboard Overhaul

### Task 12: Fix NiftyChart

**Files:**
- Modify: `src/components/NiftyChart.tsx`

- [ ] **Step 1: Use CSS variable colors**

Replace all hardcoded hex values in the chart configuration with CSS variable references. Since lightweight-charts needs JS hex values, read them from computed styles:

```typescript
const styles = getComputedStyle(document.documentElement)
const bgPrimary = styles.getPropertyValue('--color-bg-primary').trim() || '#1a1a1a'
const bgSecondary = styles.getPropertyValue('--color-bg-secondary').trim() || '#252525'
const textMuted = styles.getPropertyValue('--color-text-muted').trim() || '#666666'
const borderPrimary = styles.getPropertyValue('--color-border-primary').trim() || '#363636'
const bullColor = styles.getPropertyValue('--color-candle-bull').trim() || '#4caf50'
const bearColor = styles.getPropertyValue('--color-candle-bear').trim() || '#e53935'
```

Apply these to chart.applyOptions() layout, grid, crosshair, and candlestick series.

- [ ] **Step 2: Handle empty/closed market state**

When no candle data is available, show a centered message instead of an empty chart:

```tsx
{candles.length === 0 && !loading && (
  <div className="absolute inset-0 flex items-center justify-center text-text-muted text-sm">
    Market closed — last session data unavailable
  </div>
)}
```

- [ ] **Step 3: Fix timeframe pill styling**

Active pill: `bg-brand text-bg-primary` (green background, dark text)
Inactive pill: `text-text-muted hover:text-text-secondary`

- [ ] **Step 4: Build and commit**

```bash
npm run build
git add src/components/NiftyChart.tsx
git commit -m "fix: chart uses CSS vars, handles empty state, green active pill"
```

---

### Task 13: Fix Options Chain

**Files:**
- Modify: `src/components/OptionsChain.tsx`

- [ ] **Step 1: Restructure header layout**

Split the header into: title on left ("Options Chain"), expiry selector on right. Currently they're jammed together.

```tsx
<div className="flex items-center justify-between px-3 py-2 border-b border-border-primary">
  <h3 className="text-sm font-medium text-text-primary">Options Chain</h3>
  <div className="flex items-center gap-3">
    {snapshot?.spot_price > 0 && (
      <span className="text-xs text-text-muted">
        Spot: {snapshot.spot_price.toLocaleString('en-IN')}
      </span>
    )}
    <select ... >
      {/* expiry options */}
    </select>
  </div>
</div>
```

- [ ] **Step 2: Add market closed empty state**

When chain rows are empty, show a graceful message instead of an empty table:

```tsx
{rows.length === 0 && (
  <div className="flex flex-col items-center justify-center py-12 text-text-muted">
    <p className="text-sm">Market closed</p>
    <p className="text-xs mt-1">Option chain data will appear when market opens</p>
  </div>
)}
```

- [ ] **Step 3: Add hover states on rows**

```tsx
<tr className="hover:bg-bg-hover transition-colors cursor-pointer" ...>
```

- [ ] **Step 4: Build and commit**

```bash
npm run build
git add src/components/OptionsChain.tsx
git commit -m "feat: options chain header layout, market closed state, row hover"
```

---

### Task 14: Restructure Dashboard Right Panel

**Files:**
- Modify: `src/pages/Dashboard.tsx`
- Create: `src/components/DepthCard.tsx` (extract from Dashboard)

Currently the right panel has SignalPanel + MarketDepth + OrderTicket all crammed together with SignalPanel dominating. Restructure: OrderTicket primary, Signal as subtle banner, Depth collapsed by default.

- [ ] **Step 1: Extract DepthCard to its own file**

Move the inline DepthCard component from Dashboard.tsx to `src/components/DepthCard.tsx`. Add a collapsible toggle:

```tsx
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface DepthCardProps {
  quote: OptionQuote | null
}

export default function DepthCard({ quote }: DepthCardProps) {
  const [expanded, setExpanded] = useState(false)

  if (!quote) return null

  return (
    <div className="border-b border-border-primary">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs text-text-muted hover:bg-bg-hover"
      >
        <span>Market Depth</span>
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {expanded && (
        <div className="px-3 pb-2 animate-fade-in">
          {/* bid/ask/IV/greeks grid */}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Reorder right panel in Dashboard.tsx**

New order (top to bottom):
1. **OrderTicket** (primary — always visible, takes most space)
2. **DepthCard** (collapsed by default, expandable)
3. **SignalPanel** (subtle — only shows when a signal exists)

```tsx
<aside className="hidden md:flex md:w-[300px] flex-col border-l border-border-primary bg-bg-secondary overflow-y-auto">
  <OrderTicket />
  <DepthCard quote={selectedQuote} />
  {latestSignal && <SignalPanel />}
</aside>
```

- [ ] **Step 3: Build and commit**

```bash
npm run build
git add src/pages/Dashboard.tsx src/components/DepthCard.tsx
git commit -m "feat: restructure right panel — order ticket primary, depth collapsible, signal conditional"
```

---

### Task 15: Fix OrderTicket

**Files:**
- Modify: `src/components/OrderTicket.tsx`

- [ ] **Step 1: Compact CE/PE toggle**

Replace full-width green CE / red PE buttons with a compact pill toggle:

```tsx
<div className="inline-flex rounded-sm border border-border-primary overflow-hidden">
  <button
    onClick={() => setOptionType('CE')}
    className={`px-4 py-1.5 text-xs font-medium transition-colors ${
      optionType === 'CE'
        ? 'bg-profit text-white'
        : 'bg-bg-primary text-text-muted hover:text-text-secondary'
    }`}
  >
    CE
  </button>
  <button
    onClick={() => setOptionType('PE')}
    className={`px-4 py-1.5 text-xs font-medium transition-colors ${
      optionType === 'PE'
        ? 'bg-loss text-white'
        : 'bg-bg-primary text-text-muted hover:text-text-secondary'
    }`}
  >
    PE
  </button>
</div>
```

- [ ] **Step 2: Better disabled state hint**

When submit button is disabled, show a hint below it:

```tsx
{!selectedQuote && (
  <p className="text-xs text-text-muted text-center mt-2">
    ← Select a contract from the chain
  </p>
)}
```

- [ ] **Step 3: Remove debug text**

Remove the raw `selectedPortfolioId` and "Signal: None" text from the order ticket. These are meaningless to users.

- [ ] **Step 4: Fix lot size multiplier**

The estimated value uses hardcoded `25`. Change to `65` (current NIFTY lot size) or better, derive from a constant:

```typescript
const NIFTY_LOT_SIZE = 65
const estimatedValue = price * lots * NIFTY_LOT_SIZE
```

- [ ] **Step 5: Build and commit**

```bash
npm run build
git add src/components/OrderTicket.tsx
git commit -m "fix: compact CE/PE toggle, disabled hint, remove debug text, correct lot size"
```

---

### Task 16: Slim Down SignalPanel

**Files:**
- Modify: `src/components/SignalPanel.tsx`

- [ ] **Step 1: Make signal a subtle banner**

Replace the large dominating panel with a compact, information-dense banner:

- Reduce the large BULLISH/BEARISH badge to a small inline badge
- Show confidence as a small bar (4px height) instead of a large block
- Collapse entry/target/stop into a single compact row
- "Load Into Ticket" becomes a small text button, not a large CTA

The panel should take max 120px of vertical space when signal exists, not 300px+.

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/components/SignalPanel.tsx
git commit -m "feat: slim signal panel to compact banner"
```

---

## Chunk 6: Data Pages & Empty States

### Task 17: Create Skeleton Component

**Files:**
- Create: `src/components/Skeleton.tsx`

- [ ] **Step 1: Create reusable skeleton components**

```tsx
interface SkeletonProps {
  className?: string
}

export function SkeletonLine({ className = '' }: SkeletonProps) {
  return <div className={`skeleton h-4 rounded-sm ${className}`} />
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          {Array.from({ length: cols }).map((_, j) => (
            <SkeletonLine key={j} className="flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonCard({ className = '' }: SkeletonProps) {
  return (
    <div className={`skeleton h-24 rounded-sm ${className}`} />
  )
}
```

The `skeleton` CSS class was defined in Task 6 (globals.css).

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/components/Skeleton.tsx
git commit -m "feat: add skeleton loading components"
```

---

### Task 18: Fix Orders Page

**Files:**
- Modify: `src/pages/Orders.tsx`

- [ ] **Step 1: Better empty state**

Replace plain "No orders yet" text with a centered message and call-to-action:

```tsx
{orders.length === 0 ? (
  <div className="flex flex-col items-center justify-center py-16 text-text-muted">
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" className="mb-4 opacity-30">
      <rect x="8" y="8" width="32" height="32" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <line x1="16" y1="18" x2="32" y2="18" stroke="currentColor" strokeWidth="1.5" />
      <line x1="16" y1="24" x2="28" y2="24" stroke="currentColor" strokeWidth="1.5" />
      <line x1="16" y1="30" x2="24" y2="30" stroke="currentColor" strokeWidth="1.5" />
    </svg>
    <p className="text-sm">No orders yet</p>
    <p className="text-xs mt-1">Place your first order from the dashboard</p>
  </div>
) : (
  <table>...</table>
)}
```

- [ ] **Step 2: Consistent table headers**

Use ALL CAPS with `text-xs text-text-muted uppercase tracking-wider` for all table headers consistently.

- [ ] **Step 3: Content-based column widths**

Use fixed widths for narrow columns:

```tsx
<th className="w-16">Side</th>    {/* narrow */}
<th className="w-16">Type</th>    {/* narrow */}
<th className="w-20">Qty</th>     {/* narrow */}
<th className="">Symbol</th>      {/* flex grow */}
```

- [ ] **Step 4: Add row hover states**

```tsx
<tr className="hover:bg-bg-hover transition-colors">
```

- [ ] **Step 5: Add loading skeleton**

Show `<SkeletonTable />` when `portfolioLoading` is true.

- [ ] **Step 6: Build and commit**

```bash
npm run build
git add src/pages/Orders.tsx
git commit -m "feat: orders page empty state, consistent headers, column widths, hover, skeleton"
```

---

### Task 19: Fix Positions Page

**Files:**
- Modify: `src/pages/Positions.tsx`

Apply same patterns as Orders: empty state illustration, consistent headers, hover states, skeleton loading, content-sized columns.

- [ ] **Step 1: Apply improvements**

Same pattern as Task 18 but with positions-specific empty state text: "No open positions" / "Your active positions will appear here".

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/pages/Positions.tsx
git commit -m "feat: positions page empty state, consistent styling"
```

---

### Task 20: Fix History Page

**Files:**
- Modify: `src/pages/History.tsx`

Same improvements as Orders/Positions.

- [ ] **Step 1: Apply improvements**

Empty state: "No trade history" / "Filled orders will appear here".

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/pages/History.tsx
git commit -m "feat: history page empty state, consistent styling"
```

---

### Task 21: Fix Funds Page

**Files:**
- Modify: `src/pages/Funds.tsx`

- [ ] **Step 1: Add currency formatting**

Create a currency format helper and apply ₹ prefix to all monetary values:

```typescript
function formatCurrency(value: number): string {
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
```

Apply to all displayed monetary values in the component.

- [ ] **Step 2: Convert fund breakdown from card grid to compact table**

Replace the 3-column oversized card grid with a clean 2-column key-value table:

```tsx
<div className="mt-6">
  <h3 className="text-sm font-medium text-text-primary mb-3 px-4">Fund Breakdown</h3>
  <table className="w-full text-sm">
    <tbody>
      {breakdownItems.map(item => (
        <tr key={item.label} className="border-b border-border-secondary">
          <td className="px-4 py-2 text-text-muted">{item.label}</td>
          <td className="px-4 py-2 text-right text-text-primary font-medium tabular-nums">
            {formatCurrency(item.value)}
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

- [ ] **Step 3: Build and commit**

```bash
npm run build
git add src/pages/Funds.tsx
git commit -m "feat: funds page currency formatting (₹), compact table layout"
```

---

### Task 22: Fix Analytics Page

**Files:**
- Modify: `src/pages/Analytics.tsx`

- [ ] **Step 1: Better equity curve empty state**

Replace the large gray empty box with a placeholder flat line or message:

```tsx
{equityData.length === 0 ? (
  <div className="flex items-center justify-center h-48 text-text-muted text-sm">
    Equity curve will appear after your first trade
  </div>
) : (
  // ... existing chart
)}
```

- [ ] **Step 2: Fix P&L bar minimum width**

When a bar chart value is very small (like ₹0), it renders as a tiny dot. Set minimum visible width:

```typescript
const barWidth = Math.max(Math.abs(value) / maxValue * 100, 2) // minimum 2% width
```

- [ ] **Step 3: Add ₹ currency formatting to stat cards**

Use the same `formatCurrency` helper for the Equity stat card.

- [ ] **Step 4: Build and commit**

```bash
npm run build
git add src/pages/Analytics.tsx
git commit -m "feat: analytics empty states, minimum bar width, currency formatting"
```

---

## Chunk 7: Mobile Experience

### Task 23: Mobile Header Simplification

**Files:**
- Modify: `src/components/Header.tsx`

- [ ] **Step 1: Responsive header layout**

On mobile (< md), show only:
- Logo + "lite" text
- Spot price (compact)
- User avatar + logout

Hide on mobile:
- Nav tabs (mobile uses bottom nav)
- Portfolio selector (move to settings or a sheet)
- Full market data display

```tsx
{/* Desktop nav - hidden on mobile */}
<nav className="hidden md:flex items-center gap-1">
  {tabs.map(tab => ...)}
</nav>

{/* Desktop-only sections */}
<div className="hidden md:flex items-center gap-3">
  {/* Portfolio selector, WS status */}
</div>
```

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/components/Header.tsx
git commit -m "feat: simplified mobile header"
```

---

### Task 24: Mobile Bottom Nav Update

**Files:**
- Modify: `src/components/MobileNav.tsx`

- [ ] **Step 1: Update active state to brand green**

Change active icon color from blue (#387ed1) to brand green (#a3e635):

```tsx
className={isActive ? 'text-brand' : 'text-text-muted'}
```

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/components/MobileNav.tsx
git commit -m "feat: mobile nav green active state"
```

---

### Task 25: Streamline Mobile Order Sheet

**Files:**
- Modify: `src/pages/Dashboard.tsx`

- [ ] **Step 1: Simplify mobile bottom sheet**

Currently the mobile bottom sheet has SignalPanel + OrderTicket stacked, making it very long. Simplify to just the OrderTicket with essential fields:

```tsx
{/* Mobile order overlay */}
{showMobileTicket && (
  <div className="fixed inset-0 z-50 md:hidden">
    <div className="absolute inset-0 bg-black/60" onClick={() => setShowMobileTicket(false)} />
    <div className="absolute bottom-0 left-0 right-0 bg-bg-secondary border-t border-border-primary max-h-[70vh] overflow-y-auto animate-fade-in">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border-primary">
        <span className="text-sm font-medium text-text-primary">Place Order</span>
        <button onClick={() => setShowMobileTicket(false)} className="text-text-muted">✕</button>
      </div>
      <OrderTicket />
    </div>
  </div>
)}
```

Remove SignalPanel from the mobile overlay. Signal info can be accessed on the dashboard itself.

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/pages/Dashboard.tsx
git commit -m "feat: streamlined mobile order sheet — ticket only"
```

---

## Chunk 8: Animations, Polish & Final QA

### Task 26: Toast Animations

**Files:**
- Modify: `src/components/Toast.tsx`

- [ ] **Step 1: Add slide-in animation**

Apply the `animate-slide-in` class (defined in globals.css, Task 6) to each toast:

```tsx
<div className="animate-slide-in flex items-center gap-2 ...">
```

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/components/Toast.tsx
git commit -m "feat: toast slide-in animation"
```

---

### Task 27: Page Transition Fade

**Files:**
- Modify: `src/App.tsx`

- [ ] **Step 1: Wrap route content with fade animation**

Add `animate-fade-in` to the main content area on route change:

```tsx
<main className="flex-1 overflow-auto animate-fade-in" key={location.pathname}>
  <Routes>
    ...
  </Routes>
</main>
```

Using `key={location.pathname}` forces React to remount on route change, triggering the animation.

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/App.tsx
git commit -m "feat: page transition fade animation"
```

---

### Task 28: Table Row Hover States (Global)

**Files:**
- Modify: `src/styles/globals.css`

- [ ] **Step 1: Add global table row hover in @layer base**

```css
@layer base {
  tbody tr {
    transition: background-color 150ms;
  }
  tbody tr:hover {
    background-color: var(--color-bg-hover);
  }
}
```

This applies hover states to ALL table rows across the app without modifying each page component individually.

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/styles/globals.css
git commit -m "feat: global table row hover states"
```

---

### Task 29: Loading Skeletons in App.tsx

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/components/LoadingState.tsx`

- [ ] **Step 1: Add skeleton variant to LoadingState**

```tsx
import { SkeletonTable } from './Skeleton'

interface LoadingStateProps {
  loading: boolean
  empty: boolean
  emptyText?: string
  variant?: 'spinner' | 'skeleton'
  children: React.ReactNode
}

export default function LoadingState({ loading, empty, emptyText, variant = 'spinner', children }: LoadingStateProps) {
  if (loading) {
    return variant === 'skeleton' ? <SkeletonTable /> : <Spinner />
  }
  if (empty) {
    return <EmptyState text={emptyText} />
  }
  return <>{children}</>
}
```

- [ ] **Step 2: Build and commit**

```bash
npm run build
git add src/components/LoadingState.tsx src/App.tsx
git commit -m "feat: loading skeleton variant for LoadingState"
```

---

### Task 30: Final Build, Deploy & Visual QA

- [ ] **Step 1: Full build check**

```bash
cd /Users/proxy/trading/lite/frontend && npm run build
```

Must pass with ZERO errors and ZERO warnings.

- [ ] **Step 2: Deploy to Vercel**

```bash
cd /Users/proxy/trading/lite/frontend && npx vercel --prod --yes
```

- [ ] **Step 3: Visual QA — Desktop**

```bash
playwright screenshot --wait-for-timeout 5000 --viewport-size=1440,900 "https://litetrade.vercel.app" /tmp/desktop-home.png
playwright screenshot --wait-for-timeout 5000 --viewport-size=1440,900 "https://litetrade.vercel.app/login" /tmp/desktop-login.png
```

Verify:
- [ ] Green kite logo visible in header
- [ ] Login page has signup toggle, green CTA, password eye icon
- [ ] No "Holdings" tab in header
- [ ] No WS "connected" dot when connected
- [ ] Spot price shows "--" or real value (not "0.00")
- [ ] Chart renders without blue-tinted backgrounds
- [ ] Options chain shows "Market closed" when empty
- [ ] Order ticket has compact CE/PE toggle
- [ ] Ticker bar hidden when no data

- [ ] **Step 4: Visual QA — Mobile**

```bash
playwright screenshot --wait-for-timeout 5000 --viewport-size=390,844 "https://litetrade.vercel.app" /tmp/mobile-home.png
playwright screenshot --wait-for-timeout 5000 --viewport-size=390,844 "https://litetrade.vercel.app/login" /tmp/mobile-login.png
```

Verify:
- [ ] Header simplified on mobile
- [ ] No ticker bar on mobile
- [ ] Bottom nav has green active state
- [ ] Login page is centered and usable

- [ ] **Step 5: Final commit and push**

```bash
git add -A
git commit -m "chore: final QA pass and deploy"
git push origin ui-audit
```

---

## Appendix: Quick Reference

### Color Palette
| Token | Hex | Usage |
|-------|-----|-------|
| `brand` | `#a3e635` | Logo, CTA buttons, active indicators |
| `brand-dark` | `#8bc926` | Logo shadow/depth |
| `signal` | `#387ed1` | Links, secondary accent, info |
| `profit` | `#4caf50` | Green P&L, CE options, buy |
| `loss` | `#e53935` | Red P&L, PE options, sell |
| `bg-primary` | `#1a1a1a` | Page background |
| `bg-secondary` | `#252525` | Cards, panels |
| `bg-tertiary` | `#2a2a2a` | Inputs, hover states |
| `bg-hover` | `#2e2e2e` | Row/element hover |
| `border-primary` | `#363636` | Main dividers |
| `border-secondary` | `#2e2e2e` | Subtle separators |
| `text-primary` | `#e0e0e0` | Body text |
| `text-secondary` | `#999999` | Secondary labels |
| `text-muted` | `#666666` | Dim/placeholder text |

### Build & Deploy Commands
```bash
cd /Users/proxy/trading/lite/frontend
npm run build                     # Must pass with 0 errors
npx vercel --prod --yes           # Deploy to production
playwright screenshot --wait-for-timeout 3000 --viewport-size=1440,900 "https://litetrade.vercel.app" /tmp/verify.png
```

### Key Constraints
- NO backend modifications
- NO navy/blue tint hex codes in CSS or chart configs
- ALL custom CSS inside `@layer base`
- NO pre-filled credentials
- NO rounded corners > 2px (rounded-sm)
- NIFTY lot size: 65 (not 25)
