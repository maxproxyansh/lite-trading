# NIFTY Spot Price PiP Widget

**Date:** 2026-03-21
**Scope:** Mobile only (Android Chrome)
**API:** Document Picture-in-Picture API

## Summary

A floating pill widget that shows live NIFTY spot price when the user leaves the Lite PWA. Activated manually via a button in the header. Tap the pill to return to the app. Optional P&L row toggled via localStorage.

## User Flow

1. User taps **float button** in Header (next to existing NIFTY spot price)
2. Browser prompts for PiP permission (first time only)
3. Small pill appears as a PiP overlay
4. User switches apps — pill stays floating over other apps
5. Pill updates in real-time via existing WebSocket
6. Tap anywhere on pill → calls `pipWindow.close()` + `window.focus()` → returns to Lite

## Pill Design

### Default (spot price only)

```
┌──────────────────────────┐
│  NIFTY  23,412  +0.8%    │
└──────────────────────────┘
```

### With P&L (opt-in)

```
┌──────────────────────────┐
│  NIFTY  23,412  +0.8%    │
│  P&L  +₹2,340            │
└──────────────────────────┘
```

### Visual Specs

- **Size:** ~240x48px (default), ~240x72px (with P&L). Android Chrome enforces a minimum PiP width of ~240px — pill layout adapts to whatever the OS provides.
- **Background:** Dark (`#1a1a2e` or Lite theme dark)
- **Text:** White, bold price, smaller change %
- **Border:** 3-5px accent border — green (`#22c55e`) when positive, red (`#ef4444`) when negative
- **Border radius:** Fully rounded (pill shape)
- **Font:** System sans-serif
- **Draggable:** Yes (OS-native PiP drag behavior)

## Technical Architecture

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/hooks/usePiP.ts` | Hook managing Document PiP lifecycle (open, close, support detection) |
| `frontend/src/components/PiPWidget.tsx` | React component rendered inside PiP window (the pill UI) |
| `frontend/src/components/PiPButton.tsx` | Float button added to Header |
| `frontend/src/types/document-pip.d.ts` | TypeScript type declarations for `documentPictureInPicture` API (not in standard DOM lib) |

### Existing File Changes

| File | Change |
|------|--------|
| `frontend/src/components/Header.tsx` | Add `<PiPButton />` next to spot price (mobile only, feature-gated) |

### No Changes Needed

- `useStore.ts` — existing `snapshot` and `positions` state is sufficient
- `useWebSocket.ts` — WS stays connected in background tab, Zustand updates propagate to PiP portal

### How It Works

1. `usePiP` hook calls `documentPictureInPicture.requestWindow({ width: 240, height: 48 })`
2. Creates a React portal (`createPortal` from `react-dom`) into the PiP window's body
3. Injects a `<style>` tag into the PiP window's `<head>` with **inline CSS only** — Tailwind classes do not work in the PiP document since it's a separate DOM with no access to the parent's stylesheets. All pill styling is plain CSS injected directly.
4. Renders `PiPWidget` inside that portal
5. `PiPWidget` subscribes to Zustand store for `snapshot.spot`, `snapshot.change_pct`, and `positions`
6. WebSocket in main page stays alive — Zustand updates propagate to PiP portal automatically
7. On PiP close: `pipWindow.addEventListener('pagehide', cleanup)` tears down the React portal

### Feature Detection

```tsx
const isPiPSupported = 'documentPictureInPicture' in window;
```

Button only renders when `isPiPSupported` is true. No fallback — unsupported browsers simply don't see the button.

### Real-time Updates

- **Spot price:** from Zustand `state.snapshot.spot`, `state.snapshot.change`, `state.snapshot.change_pct` (updated by WebSocket `market.snapshot` messages)
- **P&L:** sum of `unrealized_pnl` across all items in `state.positions` for the active portfolio. When `positions` is empty, P&L row is hidden (not shown as zero).
- No new WebSocket subscriptions or API calls needed

### Stale Data Handling

If the WebSocket disconnects while PiP is open, the pill shows last-known price with a dimmed opacity (0.5) to indicate staleness. The existing `wsStatus` field in the Zustand store is used to detect this. When WS reconnects, opacity returns to normal.

## Settings

- **Show P&L in PiP** — `localStorage` key `pip-show-pnl`, default `false`
- Checked directly by `PiPWidget` — no Settings page UI needed for now

## Constraints

- **Android Chrome 116+ only** — Document PiP API not supported on iOS Safari, Firefox
- **Requires user gesture** — `requestWindow()` must be called from a user-initiated event (button tap)
- **One PiP window at a time** — browser enforces this
- **PiP window size** — OS enforces minimum dimensions (~240px wide on Android), pill layout uses flexbox to adapt
- **No custom drag** — dragging is handled by the OS PiP frame, not custom JS
- **Market closed** — pill still shows last price with static data, no special closed-market indicator (same behavior as the main Header)
