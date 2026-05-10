# NIFTY Floating Overlay — Native Android App

**Date:** 2026-03-21
**Scope:** Standalone Android app (not part of the PWA)
**Project location:** `/Users/proxy/trading/lite-widget/`

## Intent

A tiny native Android app whose sole purpose is to show a **floating pill overlay** on top of other apps, displaying the live NIFTY 50 spot price. Like YouTube Premium's floating player or Facebook Messenger chat heads — visible while using other apps, draggable, real-time updates.

This is NOT a home screen widget. It's a floating overlay using Android's `SYSTEM_ALERT_WINDOW` permission. The overlay sits above most apps but below some system UI (status bar, navigation bar) — Android controls the exact Z-ordering.

## Why Native

The Lite product is a PWA at `litetrade.vercel.app`. PWAs cannot draw over other apps — this requires native Android APIs (`WindowManager` + `TYPE_APPLICATION_OVERLAY`). This is a separate tiny app (~500 lines of Kotlin), not a rewrite.

## User Flow

1. User installs the APK (sideload, not Play Store)
2. Opens the app → sees a simple screen: API key input (first launch only) + "Start Floating Price" button
3. If `SYSTEM_ALERT_WINDOW` not granted → app opens the system "Display over other apps" settings page for this app. User toggles it on and returns to the app. App re-checks on resume (`onResume`), shows current grant status.
4. On Android 13+, if notification permission (`POST_NOTIFICATIONS`) not granted → request it. The foreground service still runs without it, but the "Stop" action in the notification won't be visible. Show a note explaining this.
5. User taps "Start" → foreground service starts, floating pill appears on screen
6. User can switch to any app — pill stays floating
7. Pill shows live NIFTY spot price, updating tick-by-tick via WebSocket
8. User can drag the pill anywhere on screen
9. Tap the pill → opens `https://litetrade.vercel.app` in the user's default browser (not hardcoded to Chrome)
10. Long-press the pill → closes the overlay and stops the service
11. A persistent foreground notification keeps the service alive (Android requirement). Notification has a "Stop" action.

## Pill Design

```
┌──────────────────────────────┐
│  NIFTY  23,412.50  +0.8%    │
└──────────────────────────────┘
```

### Visual Specs

- **Background:** Dark (`#1a1a2e`)
- **Text:** White for price, muted gray (`#94a3b8`) for "NIFTY" label
- **Change %:** Green (`#22c55e`) when positive, red (`#ef4444`) when negative
- **Border:** 4px accent border — green when positive, red when negative
- **Border radius:** Fully rounded (pill shape)
- **Font:** System default (Roboto on Android), bold for price
- **Size:** Wrap content, roughly 240dp x 48dp
- **Draggable:** Yes, via touch listener on the view
- **Elevation/shadow:** Subtle shadow so it floats visually above other content

### States

- **Connected:** Normal pill with live price
- **Disconnected/Reconnecting:** Pill at 50% opacity, shows last known price
- **Market closed:** Shows last close price, normal opacity (same as PWA Header behavior)

## Technical Architecture

### Data Source

The app connects to the existing Lite backend WebSocket for real-time market data.

**WebSocket URL:** `wss://lite-options-api-production-6c61.up.railway.app/api/v1/ws`

**Authentication:** `X-API-Key` header. The app stores an API key entered once on first launch. This is a personal-use sideloaded app — the key is stored in plain `SharedPreferences` (no EncryptedSharedPreferences to avoid extra dependencies).

**Message format (incoming):**
```json
{
  "type": "market.snapshot",
  "payload": {
    "spot_symbol": "NIFTY 50",
    "spot": 23412.50,
    "change": 187.35,
    "change_pct": 0.81,
    "market_status": "OPEN",
    ...
  }
}
```

Note: `market_status` values are uppercase: `OPEN`, `PRE-OPEN`, `CLOSED`, `HOLIDAY`.

The app only cares about `type == "market.snapshot"` messages and reads `spot`, `change`, `change_pct` from the payload.

**Keepalive:** Send `"ping"` text message every 30s. Server responds with `"pong"`.

**Reconnection:** OkHttp does NOT auto-reconnect WebSockets. On disconnect or failure, implement manual reconnection with exponential backoff (1s, 2s, 4s, max 30s). Set pill to 50% opacity while disconnected. Reset backoff on successful connection.

### Android Components

| Component | Purpose |
|-----------|---------|
| `MainActivity.kt` | Single screen: API key input (persisted), Start/Stop toggle, overlay permission flow, notification permission (Android 13+) |
| `FloatingService.kt` | Foreground service owning the pill view, WebSocket connection, drag handling, saved position, and notification |
| `NiftyWebSocket.kt` | OkHttp WebSocket client — connects with `X-API-Key`, parses `market.snapshot`, handles ping/pong, reconnects with backoff |

### Dependencies

- **OkHttp** — WebSocket client
- **`org.json`** — JSON parsing (built into Android, no extra dependency)
- Nothing else. Keep it minimal.

### Key Implementation Details

**Floating View (WindowManager):**
```kotlin
val params = WindowManager.LayoutParams(
    WindowManager.LayoutParams.WRAP_CONTENT,
    WindowManager.LayoutParams.WRAP_CONTENT,
    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
    PixelFormat.TRANSLUCENT
)
params.gravity = Gravity.TOP or Gravity.START
params.x = savedX
params.y = savedY
windowManager.addView(pillView, params)
```

**Drag handling:**
- `OnTouchListener` on the pill view
- `ACTION_DOWN` records initial touch position and initial `params.x/y`
- `ACTION_MOVE` updates `params.x` and `params.y`, calls `windowManager.updateViewLayout()`
- Small move threshold (~10px) to distinguish drag from tap
- On drag end, save position to `SharedPreferences`
- On configuration change (rotation, display resize), clamp saved position to visible screen bounds

**Foreground Service (Android 14+ compatible):**

In `AndroidManifest.xml`, the service must declare:
```xml
<service
    android:name=".FloatingService"
    android:foregroundServiceType="specialUse"
    android:exported="false">
    <property
        android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"
        android:value="Floating market data overlay displaying real-time stock prices" />
</service>
```

This is required for `targetSdkVersion 34` (Android 14). Without the `foregroundServiceType` and the `PROPERTY_SPECIAL_USE_FGS_SUBTYPE`, the service will fail to start.

- Shows a persistent notification: "NIFTY spot price overlay active"
- Notification channel: created in `onCreate`
- Notification has a "Stop" action button (PendingIntent that stops the service)
- On Android 13+, notification visibility depends on `POST_NOTIFICATIONS` permission. If denied, the service still runs but the notification is hidden — the user can only close via long-press on the pill.

**Tap to open PWA:**
```kotlin
val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://litetrade.vercel.app"))
intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
startActivity(intent)
```
Opens in the user's default browser, not hardcoded to Chrome.

**API Key Storage:**
- `SharedPreferences` with key `"api_key"`
- Entered once on first launch in MainActivity
- Passed to WebSocket connection as `X-API-Key` header
- This is a personal-use sideloaded app; plain SharedPreferences is acceptable

### Project Structure

```
lite-widget/
├── app/
│   ├── src/main/
│   │   ├── java/com/lite/widget/
│   │   │   ├── MainActivity.kt
│   │   │   ├── FloatingService.kt
│   │   │   └── NiftyWebSocket.kt
│   │   ├── res/
│   │   │   ├── layout/
│   │   │   │   ├── activity_main.xml
│   │   │   │   └── floating_pill.xml
│   │   │   ├── drawable/
│   │   │   │   └── pill_background.xml
│   │   │   └── values/
│   │   │       ├── colors.xml
│   │   │       └── strings.xml
│   │   └── AndroidManifest.xml
│   └── build.gradle.kts
├── build.gradle.kts
├── settings.gradle.kts
└── gradle/
```

### Permissions (AndroidManifest.xml)

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />  <!-- Android 13+ -->
```

### Min SDK

- `minSdkVersion 26` (Android 8.0) — required for `TYPE_APPLICATION_OVERLAY` and notification channels
- `targetSdkVersion 34`

## What This Is NOT

- Not a full trading app — no order placement, no portfolio view, no charts
- Not a Play Store app — sideloaded APK for personal use
- Not a replacement for the PWA — the PWA remains the main product
- Not a home screen widget — it's a floating overlay

## Success Criteria

1. Floating pill visible on top of other apps after tapping Start
2. Live NIFTY price updates tick-by-tick via WebSocket
3. Pill draggable to any screen position, position persisted across sessions
4. Tap pill opens Lite PWA in default browser
5. Long-press closes the pill and stops the service
6. Survives app switches, screen rotation (with position clamping), going home
7. Clean reconnection with exponential backoff on network changes
8. Foreground notification present with Stop action (visibility depends on notification permission)
9. Total codebase under 500 lines of Kotlin
10. Overlay permission flow handles the system settings redirect correctly
