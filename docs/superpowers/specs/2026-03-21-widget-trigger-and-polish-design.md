# Widget Trigger UX + PWA Cleanup + Android Widget Polish

**Date:** 2026-03-21
**Scope:** Lite PWA frontend + backend + Android widget app (`/Users/proxy/trading/lite-widget/`, already exists)

## Summary

Clean up failed web PiP code from main, add a zero-friction widget setup experience in the PWA for mobile users (one-time claim token flow — user never sees an API key), and polish the Android floating widget app (icon, branding, URL scheme, battery note).

---

## 1. PWA Cleanup — Remove Web PiP Code

Delete all web PiP files from main. No stubs, no comments.

**Delete:**
- `frontend/src/hooks/usePiP.ts`
- `frontend/src/components/PiPWidget.tsx`
- `frontend/src/components/PiPButton.tsx`
- `frontend/src/types/document-pip.d.ts`

**Modify:**
- `frontend/src/components/Header.tsx` — remove PiPButton import and `<span className="md:hidden"><PiPButton /></span>` line

---

## 2. Widget Trigger — Header Icon (Android Mobile Only)

A 28px circular button in the header, placed **outside** the NIFTY price `<div>` (the one with `optionChartSymbol` click handler) to avoid click conflicts. Positioned as a sibling after the price div, within the left section. Only visible on Android mobile — hidden on desktop (`md:hidden`) and hidden on iOS (user-agent check for Android).

**Visual specs:**
- Size: 28px circle
- Background: `#252525`
- Border: `1px solid #363636`
- Icon: Pulse/heartbeat SVG polyline (`points="2,12 6,12 9,4 12,20 15,8 18,12 22,12"`) in brand green `#a3e635`, stroke-width 2.5
- Border radius: 50%

**Behavior:**
- If Lite Pulse is already set up (check `localStorage` key `pulse-connected`): launch via hidden iframe `litewidget://start`. Iframe removed after 500ms. No navigation, no error.
- If not set up: show the onboarding modal (Section 3) instead, regardless of login count.

**File:** Create `frontend/src/components/WidgetButton.tsx`

---

## 3. Widget Trigger — Onboarding Modal + Claim Token Flow

On the **3rd login** (or when header pulse icon is tapped before setup), show a modal prompting the user to set up the widget app. Styled identically to the existing fingerprint login prompt in `App.tsx`.

### Trigger logic

- In `frontend/src/pages/Login.tsx`, on successful login (inside the login form's submit success handler, after `setSession`), increment `localStorage` counter `login-count`
- In `frontend/src/App.tsx`, after the fingerprint prompt logic, check: if `login-count >= 3` AND `pulse-prompt-dismissed` is not set in localStorage AND `pulse-connected` is not set AND user agent is Android → show the modal
- After "Skip" is tapped, set `pulse-prompt-dismissed = true` in localStorage
- After successful setup, set `pulse-connected = true` in localStorage
- Never shows again after dismissal or successful setup

### Modal content

- **Icon:** Pulse/heartbeat SVG in brand green, ~40px, centered above title
- **Title:** "Get NIFTY on your screen, always"
- **Subtitle:** "Install Lite Pulse for a floating price overlay that stays visible across all your apps."
- **Buttons:** "Skip" (left, subtle) | "Set Up" (right, brand-colored)

### "Set Up" flow (step-by-step in the same modal)

**Step 1 — Download:**
Modal shows: "First, download and install Lite Pulse" with a "Download APK" button. Button calls `POST /api/v1/agent/pulse/setup` (see Section 8) which returns `{ "claim_token": "abc123", "apk_url": "https://..." }`. Opens the APK URL for download. Stores the claim token in memory (not localStorage — it's one-time use). Shows a "Next" button once download starts.

**Step 2 — Open & Connect:**
Modal shows: "Now open Lite Pulse — it will connect automatically" with an "Open Lite Pulse" button. Button launches `litewidget://start?token=<claim_token>` via hidden iframe. Sets `pulse-connected = true` in localStorage. Modal closes.

If the user has already installed the APK (returning to complete setup), they skip Step 1.

**File:** Create `frontend/src/components/WidgetPrompt.tsx`

**Integration:** Add to `frontend/src/App.tsx` alongside the existing fingerprint prompt, gated by the login-count + dismissal + Android UA checks.

---

## 4. Lite Pulse Settings Card (PWA)

A small card in the **Settings page** (`frontend/src/pages/Settings.tsx`) for managing the Lite Pulse connection.

**Card content:**
- **Header:** "Lite Pulse" with pulse icon
- **Connected state:** Shows "Connected" with green checkmark. "Regenerate Key" button (calls the setup endpoint again, shows new claim token in a copyable field). "Disconnect" button (revokes the key, clears `pulse-connected`).
- **Not connected state:** Shows "Not connected" with a "Set Up" button that opens the onboarding modal.

**Security:**
- The actual API key is never shown in the UI — only the claim token (which expires in 10 minutes and is single-use)
- "Regenerate Key" creates a new key (revoking the old one) and shows a new claim token
- The key prefix (e.g., `lite_abc...`) can be shown for identification, but never the full key

**Responsive:** Works on both mobile and desktop (desktop users can still set up — they'd need to transfer the APK to their phone separately, but the key management works from any device).

**File:** Create `frontend/src/components/PulseSettings.tsx`, integrate into `Settings.tsx`

---

## 5. Backend — Claim Token Endpoints

New endpoints for the zero-friction setup flow.

### `POST /api/v1/agent/pulse/setup`

**Auth:** Requires logged-in user (session cookie or bearer token).

**Behavior:**
1. Creates (or rotates) an agent API key named `"lite-pulse"` for the user, with 365-day expiry, scoped to `["events:read", "signals:read", "funds:read"]` (read-only market data — no trading permissions)
2. Generates a one-time claim token (random 32-char string), stores it in DB with: `user_id`, `api_key_id`, `created_at`, `expires_at` (10 minutes), `claimed` (boolean, default false)
3. Returns: `{ "claim_token": "<token>", "apk_url": "<url>", "key_prefix": "lite_abc..." }`

### `POST /api/v1/agent/pulse/claim`

**Auth:** None (the token IS the auth).

**Request:** `{ "token": "<claim_token>" }`

**Behavior:**
1. Lookup token in DB
2. Validate: exists, not expired (< 10 min), not already claimed
3. Mark as claimed
4. Return the real API key: `{ "api_key": "lite_full_key_here" }`
5. If invalid/expired/claimed → 401

### `DELETE /api/v1/agent/pulse/setup`

**Auth:** Requires logged-in user.

**Behavior:** Revokes the user's `lite-pulse` agent key. Clears any unclaimed tokens.

**DB model:** New `PulseClaimToken` table:
- `id` (UUID)
- `user_id` (FK)
- `api_key_id` (FK)
- `token_hash` (hashed, never store raw)
- `created_at`
- `expires_at`
- `claimed` (boolean)

**Files:**
- Create `backend/routers/pulse.py` — the 3 endpoints
- Create DB migration for `PulseClaimToken` table
- Update `backend/main.py` to include the pulse router

---

## 6. Android Widget App — Custom Icon

Replace the default Android icon with a pulse/heartbeat line on dark background.

The `lite-widget/` project already exists at `/Users/proxy/trading/lite-widget/` with a working build.

**Specs:**
- Adaptive icon with `#1a1a1a` background
- Foreground: pulse/heartbeat polyline in `#a3e635` (same SVG as PWA header icon)
- Vector drawable for foreground, solid color for background

**Files (all under `lite-widget/`):**
- Create `app/src/main/res/drawable/ic_launcher_foreground.xml` (vector drawable)
- Create `app/src/main/res/drawable/ic_launcher_background.xml` (solid dark color)
- Create `app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` (adaptive icon)
- Create `app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml` (adaptive icon)

---

## 7. Android Widget App — Custom URL Scheme + Token Claim

Register `litewidget://start` intent filter so the PWA can launch the widget app.

**`lite-widget/app/src/main/AndroidManifest.xml`** — add second intent-filter to MainActivity:
```xml
<intent-filter>
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="litewidget" android:host="start" />
</intent-filter>
```

**`MainActivity.kt`** — on `litewidget://start` intent:
- Extract `token` query param from intent URI if present
- If token present → call `POST /api/v1/agent/pulse/claim` with the token, store returned API key in SharedPreferences, then auto-start FloatingService and `finish()`
- If no token but API key already saved → auto-start FloatingService and `finish()`
- Otherwise → show normal setup screen

The **manual API key input** stays as a fallback in the setup screen for power users, but is visually de-emphasized (collapsed/secondary section: "Enter key manually" expandable).

---

## 8. Android Widget App — Battery Optimization Note

In `activity_main.xml`, below the Start/Stop button, add a small informational text:

> "If the overlay stops working in the background, disable battery optimization for this app in Android Settings."

**Specs:**
- Text color: `#999999` (muted)
- Font size: 12sp
- No button/link to settings — just informational
- Visible always, not conditional

---

## 9. Android Widget App — Lite Pulse Branded Setup Screen

Rename the app from "Lite Widget" to **"Lite Pulse"** (matches the heartbeat/pulse icon theme).

The current `activity_main.xml` is default Android Material with white background and system buttons. Redesign to match Lite's dark theme and brand identity.

**Theme:**
- Background: `#1a1a1a` (Lite `bg-primary`)
- Card/section backgrounds: `#252525` (Lite `bg-secondary`)
- Text primary: `#e0e0e0`
- Text secondary/muted: `#999999`
- Borders: `#363636`
- Accent/buttons: `#a3e635` (Lite `brand`)
- Button text on accent: `#1a1a1a` (dark on green)
- Error/warning: `#e53935`

**Layout structure (top to bottom):**

1. **Header area** — pulse icon (40dp, brand green) + "Lite Pulse" title + subtitle "Floating NIFTY overlay". Similar layout to the Lite PWA login screen header.

2. **Status cards** — each permission/setup step in its own rounded card (`#252525` bg, `#363636` border, 12dp corner radius, 16dp padding):
   - **Overlay Permission** — status text (granted/not granted) with a green checkmark or red X icon. "Grant Permission" button if not granted (brand green bg, dark text).
   - **Notification Permission** (Android 13+ only) — same card style. Brief note about what it controls.
   - **API Key** — shows "Connected" with green checkmark if key is saved. Collapsed "Enter key manually" section for power users (dark bg input field, `#2a2a2a`, `#363636` border, white text, brand green cursor, "Save" button).

3. **Start/Stop button** — full-width, prominent. Brand green background when stopped ("Start Floating Price"), red background when running ("Stop Floating Price"). Rounded corners (12dp), bold text.

4. **Battery note** — muted text below the button.

**Android theme (styles.xml):**
- Use `Theme.Material3.DayNight.NoActionBar` as parent
- Override `colorSurface`, `colorOnSurface`, `android:windowBackground`, `android:statusBarColor` to match Lite dark theme
- Status bar: `#1a1a1a`, navigation bar: `#1a1a1a`

**Files to create/modify (all under `lite-widget/`):**
- Rewrite `app/src/main/res/layout/activity_main.xml` — new dark-themed layout
- Create `app/src/main/res/values/themes.xml` — dark Material theme
- Update `app/src/main/res/values/colors.xml` — add all Lite theme colors
- Update `app/src/main/res/values/strings.xml` — rename to "Lite Pulse", update labels
- Update `app/src/main/AndroidManifest.xml` — reference new theme, update app label
- Update `app/src/main/java/com/lite/widget/MainActivity.kt` — token claim HTTP call, auto-start logic, collapsible manual key section

---

## What This Does NOT Include

- No auto-update mechanism for the APK (out of scope)
- No P&L display in the widget pill (keep it simple)
- No home screen widget (separate feature, separate scope)
- No auto-start on boot
- No changes to the widget pill design (already polished in previous iteration)
- No iOS support for the widget trigger — button hidden on iOS since the Android widget app doesn't exist on iOS
- No full API key management UI — just the Lite Pulse-specific card in Settings
