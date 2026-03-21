# Lite Pulse Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean PWA of broken PiP code, add zero-friction Lite Pulse widget trigger with one-time claim token flow, and polish the Android floating overlay app with Lite branding.

**Architecture:** 3 phases — backend first (claim token endpoints), then PWA frontend (cleanup + trigger UI), then Android app (branding + URL scheme + token claim). Backend must be done before the other two. PWA and Android phases are independent of each other.

**Tech Stack:** Python/FastAPI (backend), React 19/Vite/Tailwind (frontend), Kotlin/Android (widget app)

**Spec:** `docs/superpowers/specs/2026-03-21-widget-trigger-and-polish-design.md`

---

## File Map

### Phase 1: Backend — Claim Token Endpoints

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/models.py` | Modify | Add `PulseClaimToken` model |
| `backend/schemas.py` | Modify | Add request/response schemas for pulse endpoints |
| `backend/routers/pulse.py` | Create | 3 endpoints: setup, claim, delete |
| `backend/main.py` | Modify | Register pulse router |
| `backend/tests/test_app.py` | Modify | Tests for the 3 endpoints |

### Phase 2: PWA Frontend — Cleanup + Trigger UI

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/hooks/usePiP.ts` | Delete | Remove broken PiP hook |
| `frontend/src/components/PiPWidget.tsx` | Delete | Remove PiP widget |
| `frontend/src/components/PiPButton.tsx` | Delete | Remove PiP button |
| `frontend/src/types/document-pip.d.ts` | Delete | Remove PiP types |
| `frontend/src/components/Header.tsx` | Modify | Remove PiP import/usage, add WidgetButton |
| `frontend/src/components/WidgetButton.tsx` | Create | Pulse icon in header, launches widget via iframe |
| `frontend/src/components/WidgetPrompt.tsx` | Create | Onboarding modal (download + connect steps) |
| `frontend/src/components/PulseSettings.tsx` | Create | Settings card for managing Pulse connection |
| `frontend/src/lib/api.ts` | Modify | Add pulse API functions |
| `frontend/src/pages/Login.tsx` | Modify | Increment login-count on success |
| `frontend/src/pages/Settings.tsx` | Modify | Add PulseSettings card |
| `frontend/src/App.tsx` | Modify | Add WidgetPrompt with login-count gate |

### Phase 3: Android App — Branding + URL Scheme + Token Claim

| File | Action | Responsibility |
|------|--------|----------------|
| `lite-widget/app/src/main/res/values/colors.xml` | Modify | Full Lite color palette |
| `lite-widget/app/src/main/res/values/strings.xml` | Modify | Rename to "Lite Pulse" |
| `lite-widget/app/src/main/res/values/themes.xml` | Create | Dark theme matching Lite |
| `lite-widget/app/src/main/res/layout/activity_main.xml` | Rewrite | Dark branded layout with status cards |
| `lite-widget/app/src/main/res/drawable/ic_launcher_foreground.xml` | Create | Pulse line vector drawable |
| `lite-widget/app/src/main/res/drawable/ic_launcher_background.xml` | Create | Dark solid color |
| `lite-widget/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` | Create | Adaptive icon |
| `lite-widget/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml` | Create | Adaptive icon (round) |
| `lite-widget/app/src/main/AndroidManifest.xml` | Modify | URL scheme intent filter, theme, app label |
| `lite-widget/app/src/main/java/com/lite/widget/MainActivity.kt` | Rewrite | Token claim, auto-start, dark UI bindings, collapsible manual key |
| `lite-widget/app/build.gradle.kts` | Modify | Add Material Components dependency |

---

## Phase 1: Backend

### Task 1: PulseClaimToken Model + Schemas

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/schemas.py`

- [ ] **Step 1: Add PulseClaimToken model to models.py**

Add after the `AgentApiKey` class:

```python
class PulseClaimToken(Base, BaseModelMixin):
    __tablename__ = "pulse_claim_tokens"

    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    api_key_id = Column(String(64), ForeignKey("agent_api_keys.id"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    claimed = Column(Boolean, nullable=False, default=False)
```

- [ ] **Step 2: Add schemas to schemas.py**

```python
class PulseSetupResponse(BaseModel):
    claim_token: str
    apk_url: str
    key_prefix: str

class PulseClaimRequest(BaseModel):
    token: str = Field(min_length=1)

class PulseClaimResponse(BaseModel):
    api_key: str

class PulseStatusResponse(BaseModel):
    connected: bool
    key_prefix: str | None = None
    created_at: datetime | None = None
```

- [ ] **Step 3: Verify**

Run: `cd /Users/proxy/trading/lite/backend && python3 -c "from models import PulseClaimToken; from schemas import PulseSetupResponse, PulseClaimRequest, PulseClaimResponse, PulseStatusResponse; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/schemas.py
git commit -m "feat(pulse): add PulseClaimToken model and schemas"
```

---

### Task 2: Pulse Router — Setup, Claim, Delete Endpoints

**Files:**
- Create: `backend/routers/pulse.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create backend/routers/pulse.py**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models import AgentApiKey, Portfolio, PulseClaimToken, User
from schemas import PulseClaimRequest, PulseClaimResponse, PulseSetupResponse, PulseStatusResponse
from security import hash_secret, key_prefix
from services.auth_service import get_current_user, make_agent_secret, _normalize_scopes

settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/agent/pulse", tags=["pulse"])

PULSE_KEY_NAME = "lite-pulse"
PULSE_SCOPES = ["events:read", "signals:read", "funds:read"]
PULSE_APK_URL = settings.pulse_apk_url if hasattr(settings, 'pulse_apk_url') else ""
TOKEN_EXPIRY_MINUTES = 10


@router.post("/setup", response_model=PulseSetupResponse)
def pulse_setup(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate or rotate a Lite Pulse API key and return a one-time claim token."""
    # Find or create agent portfolio
    portfolio = db.query(Portfolio).filter(
        Portfolio.user_id == user.id,
        Portfolio.kind == "agent",
    ).first()
    if not portfolio:
        raise HTTPException(status_code=400, detail="No agent portfolio found. Create one first.")

    # Revoke any existing pulse key
    existing = db.query(AgentApiKey).filter(
        AgentApiKey.user_id == user.id,
        AgentApiKey.name == PULSE_KEY_NAME,
        AgentApiKey.revoked_at.is_(None),
    ).first()
    if existing:
        existing.revoked_at = datetime.now(timezone.utc)

    # Invalidate any unclaimed tokens for this user
    db.query(PulseClaimToken).filter(
        PulseClaimToken.user_id == user.id,
        PulseClaimToken.claimed.is_(False),
    ).update({"claimed": True})

    # Create new agent key
    secret = make_agent_secret()
    api_key = AgentApiKey(
        name=PULSE_KEY_NAME,
        user_id=user.id,
        portfolio_id=portfolio.id,
        key_prefix=key_prefix(secret),
        key_hash=hash_secret(secret),
        scopes=_normalize_scopes(PULSE_SCOPES),
        is_active=True,
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        revoked_at=None,
    )
    db.add(api_key)
    db.flush()

    # Create claim token
    raw_token = token_urlsafe(32)
    claim = PulseClaimToken(
        user_id=user.id,
        api_key_id=api_key.id,
        token_hash=hash_secret(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES),
        claimed=False,
    )
    db.add(claim)
    db.commit()

    return PulseSetupResponse(
        claim_token=raw_token,
        apk_url=PULSE_APK_URL,
        key_prefix=api_key.key_prefix,
    )


@router.post("/claim", response_model=PulseClaimResponse)
def pulse_claim(
    payload: PulseClaimRequest,
    db: Session = Depends(get_db),
):
    """Exchange a one-time claim token for the real API key. No auth required."""
    token_hash = hash_secret(payload.token)
    claim = db.query(PulseClaimToken).filter(
        PulseClaimToken.token_hash == token_hash,
    ).first()

    if not claim:
        raise HTTPException(status_code=401, detail="Invalid token")
    if claim.claimed:
        raise HTTPException(status_code=401, detail="Token already used")
    if claim.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired")

    claim.claimed = True

    api_key = db.query(AgentApiKey).filter(
        AgentApiKey.id == claim.api_key_id,
        AgentApiKey.revoked_at.is_(None),
        AgentApiKey.is_active.is_(True),
    ).first()

    if not api_key:
        raise HTTPException(status_code=401, detail="Associated key revoked")

    # We need the raw secret — but we only stored the hash.
    # Solution: store the encrypted secret on the AgentApiKey temporarily,
    # or re-generate. Since we just created the key in /setup, we can't recover it.
    # Better approach: store the raw secret on the claim token itself (encrypted).
    #
    # REVISED: Store the raw API secret alongside the claim token hash.
    # The claim token row has a `secret_encrypted` field for this.
    raise HTTPException(status_code=501, detail="TODO: needs secret storage on claim token")


@router.delete("/setup")
def pulse_disconnect(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revoke the user's Lite Pulse key and clear unclaimed tokens."""
    existing = db.query(AgentApiKey).filter(
        AgentApiKey.user_id == user.id,
        AgentApiKey.name == PULSE_KEY_NAME,
        AgentApiKey.revoked_at.is_(None),
    ).first()
    if existing:
        existing.revoked_at = datetime.now(timezone.utc)

    db.query(PulseClaimToken).filter(
        PulseClaimToken.user_id == user.id,
        PulseClaimToken.claimed.is_(False),
    ).update({"claimed": True})

    db.commit()
    return {"ok": True}


@router.get("/status", response_model=PulseStatusResponse)
def pulse_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check if the user has an active Lite Pulse key."""
    existing = db.query(AgentApiKey).filter(
        AgentApiKey.user_id == user.id,
        AgentApiKey.name == PULSE_KEY_NAME,
        AgentApiKey.revoked_at.is_(None),
        AgentApiKey.is_active.is_(True),
    ).first()
    if existing:
        return PulseStatusResponse(connected=True, key_prefix=existing.key_prefix, created_at=existing.created_at)
    return PulseStatusResponse(connected=False)
```

Wait — I hit a design problem in the `/claim` endpoint. We hash the API secret when storing it, so we can't return it later. The claim token needs to carry the raw secret.

**Revised approach:** Add a `secret_ciphertext` column to `PulseClaimToken` that stores the raw API secret encrypted with a server-side key (or just the raw secret — it's a short-lived row that gets marked as claimed immediately). Since the claim token itself is the auth and it's single-use, storing the raw secret on the claim row is acceptable security-wise.

Let me revise the model and code.

- [ ] **Step 1 (revised): Update PulseClaimToken model**

```python
class PulseClaimToken(Base, BaseModelMixin):
    __tablename__ = "pulse_claim_tokens"

    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    api_key_id = Column(String(64), ForeignKey("agent_api_keys.id"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    api_secret = Column(String(255), nullable=False)  # raw API secret, cleared after claim
    expires_at = Column(DateTime(timezone=True), nullable=False)
    claimed = Column(Boolean, nullable=False, default=False)
```

The `api_secret` field stores the raw secret temporarily. After `/claim` is called, the row is marked claimed and the secret is cleared.

- [ ] **Step 2: Create backend/routers/pulse.py with the corrected /claim endpoint**

The `/claim` endpoint reads `claim.api_secret`, returns it, then sets `claim.api_secret = ""` and `claim.claimed = True`.

- [ ] **Step 3: Add `pulse_apk_url` to config.py Settings**

```python
pulse_apk_url: str = Field(default="", alias="PULSE_APK_URL")
```

- [ ] **Step 4: Register router in main.py**

Add to imports: `from routers import pulse`
Add to router includes: `app.include_router(pulse.router)`

- [ ] **Step 5: Run tests**

Run: `cd /Users/proxy/trading/lite/backend && python3 -m pytest tests/test_app.py -x -q --tb=short`

- [ ] **Step 6: Commit**

```bash
git add backend/models.py backend/schemas.py backend/routers/pulse.py backend/main.py backend/config.py
git commit -m "feat(pulse): add claim token endpoints for zero-friction Lite Pulse setup"
```

---

### Task 3: Backend Tests for Pulse Endpoints

**Files:**
- Modify: `backend/tests/test_app.py`

- [ ] **Step 1: Add tests**

Add tests for:
1. `POST /api/v1/agent/pulse/setup` — creates key + claim token, returns token + apk_url
2. `POST /api/v1/agent/pulse/claim` — exchanges token for API key, token can't be reused
3. `POST /api/v1/agent/pulse/claim` with expired token → 401
4. `POST /api/v1/agent/pulse/claim` with already-claimed token → 401
5. `DELETE /api/v1/agent/pulse/setup` — revokes key
6. `GET /api/v1/agent/pulse/status` — returns connected/disconnected
7. `POST /api/v1/agent/pulse/setup` twice — rotates key, invalidates old token

Pattern: follow existing test style in the file (uses `TestClient`, `admin_headers` fixture, etc.)

- [ ] **Step 2: Run tests**

Run: `cd /Users/proxy/trading/lite/backend && python3 -m pytest tests/test_app.py -x -q --tb=short`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_app.py
git commit -m "test(pulse): add tests for claim token setup/claim/revoke flow"
```

---

## Phase 2: PWA Frontend

### Task 4: Remove Web PiP Code

**Files:**
- Delete: `frontend/src/hooks/usePiP.ts`
- Delete: `frontend/src/components/PiPWidget.tsx`
- Delete: `frontend/src/components/PiPButton.tsx`
- Delete: `frontend/src/types/document-pip.d.ts`
- Modify: `frontend/src/components/Header.tsx`

- [ ] **Step 1: Delete PiP files**

```bash
rm frontend/src/hooks/usePiP.ts frontend/src/components/PiPWidget.tsx frontend/src/components/PiPButton.tsx frontend/src/types/document-pip.d.ts
```

- [ ] **Step 2: Clean Header.tsx**

Remove line 5 (`import PiPButton from '../components/PiPButton'`) and line 56 (`<span className="md:hidden"><PiPButton /></span>`).

- [ ] **Step 3: Verify build**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit && npx vite build 2>&1 | tail -5`

- [ ] **Step 4: Commit**

```bash
git add -A frontend/src/hooks/usePiP.ts frontend/src/components/PiPWidget.tsx frontend/src/components/PiPButton.tsx frontend/src/types/document-pip.d.ts frontend/src/components/Header.tsx
git commit -m "fix: remove broken web PiP code from main"
```

---

### Task 5: Pulse API Functions + WidgetButton Component

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/components/WidgetButton.tsx`
- Modify: `frontend/src/components/Header.tsx`

- [ ] **Step 1: Add pulse API functions to api.ts**

```typescript
export async function pulseSetup(): Promise<{ claim_token: string; apk_url: string; key_prefix: string }> {
  return request('POST', '/api/v1/agent/pulse/setup')
}

export async function pulseClaim(token: string): Promise<{ api_key: string }> {
  return request('POST', '/api/v1/agent/pulse/claim', { token })
}

export async function pulseDisconnect(): Promise<void> {
  await request('DELETE', '/api/v1/agent/pulse/setup')
}

export async function pulseStatus(): Promise<{ connected: boolean; key_prefix: string | null; created_at: string | null }> {
  return request('GET', '/api/v1/agent/pulse/status')
}
```

- [ ] **Step 2: Create WidgetButton.tsx**

```tsx
import { useCallback } from 'react'

const isAndroid = /android/i.test(navigator.userAgent)

function launchWidget(token?: string) {
  const url = token ? `litewidget://start?token=${token}` : 'litewidget://start'
  const iframe = document.createElement('iframe')
  iframe.style.display = 'none'
  iframe.src = url
  document.body.appendChild(iframe)
  setTimeout(() => iframe.remove(), 500)
}

export default function WidgetButton({ onSetupNeeded }: { onSetupNeeded: () => void }) {
  const handleClick = useCallback(() => {
    const connected = localStorage.getItem('pulse-connected') === 'true'
    if (connected) {
      launchWidget()
    } else {
      onSetupNeeded()
    }
  }, [onSetupNeeded])

  if (!isAndroid) return null

  return (
    <button
      onClick={handleClick}
      className="md:hidden flex h-7 w-7 items-center justify-center rounded-full bg-bg-secondary border border-border-primary transition-colors hover:bg-bg-hover"
      title="Lite Pulse"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#a3e635"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polyline points="2,12 6,12 9,4 12,20 15,8 18,12 22,12" />
      </svg>
    </button>
  )
}

export { launchWidget }
```

- [ ] **Step 3: Add WidgetButton to Header.tsx**

Add import: `import WidgetButton from '../components/WidgetButton'`

Place **outside** the NIFTY price div (line 57), as a sibling after it within the left section `<div className="flex items-center gap-3 pl-3 pr-2">`:

```tsx
        </div>
        <WidgetButton onSetupNeeded={() => {/* will be wired in Task 7 */}} />
      </div>
```

- [ ] **Step 4: Verify build**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/WidgetButton.tsx frontend/src/components/Header.tsx
git commit -m "feat(pulse): add WidgetButton header icon and pulse API functions"
```

---

### Task 6: WidgetPrompt Onboarding Modal

**Files:**
- Create: `frontend/src/components/WidgetPrompt.tsx`

- [ ] **Step 1: Create WidgetPrompt.tsx**

A two-step modal matching the fingerprint prompt style from App.tsx (lines 361-401). Step 1: download APK. Step 2: open & connect.

The component receives `onClose` prop. It calls `pulseSetup()` to get the claim token, handles the download URL, and launches `litewidget://start?token=xxx`.

Use the same CSS classes/structure as the fingerprint prompt: fixed position bottom-right card, `z-50`, `w-[280px]`, rounded, border, shadow.

Pulse icon SVG (same polyline) at 28px, centered. Title, subtitle, then action buttons.

- [ ] **Step 2: Verify build**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/WidgetPrompt.tsx
git commit -m "feat(pulse): add onboarding modal with claim token flow"
```

---

### Task 7: Wire WidgetPrompt into App.tsx + Login Count

**Files:**
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add login count increment to Login.tsx**

In the `handleSubmit` success path (after `addToast('success', ...)`), add:

```typescript
const count = parseInt(localStorage.getItem('login-count') ?? '0', 10)
localStorage.setItem('login-count', String(count + 1))
```

Also increment after passkey login success in `handlePasskeyLogin`.

- [ ] **Step 2: Add WidgetPrompt to App.tsx**

Import `WidgetPrompt` and add state: `const [showPulsePrompt, setShowPulsePrompt] = useState(false)`

After the passkey prompt logic, add:

```tsx
useEffect(() => {
  if (!user) return
  const isAndroid = /android/i.test(navigator.userAgent)
  const count = parseInt(localStorage.getItem('login-count') ?? '0', 10)
  const dismissed = localStorage.getItem('pulse-prompt-dismissed') === 'true'
  const connected = localStorage.getItem('pulse-connected') === 'true'
  if (isAndroid && count >= 3 && !dismissed && !connected) {
    setShowPulsePrompt(true)
  }
}, [user])
```

Render the prompt (after the fingerprint prompt JSX):

```tsx
{showPulsePrompt && (
  <WidgetPrompt onClose={() => {
    setShowPulsePrompt(false)
    localStorage.setItem('pulse-prompt-dismissed', 'true')
  }} />
)}
```

Wire the Header's `WidgetButton` `onSetupNeeded` to `setShowPulsePrompt(true)` — pass it down via props or a simple callback. Since Header is rendered in App.tsx, this is straightforward.

- [ ] **Step 3: Verify build**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit && npx vite build 2>&1 | tail -5`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Login.tsx frontend/src/App.tsx
git commit -m "feat(pulse): wire onboarding modal with login count gate"
```

---

### Task 8: PulseSettings Card in Settings Page

**Files:**
- Create: `frontend/src/components/PulseSettings.tsx`
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: Create PulseSettings.tsx**

A card matching the existing Settings page style (`rounded bg-bg-secondary p-4`). Shows:
- Connected: key prefix, created date, "Regenerate" and "Disconnect" buttons
- Not connected: "Set Up" button that triggers the onboarding modal

Calls `pulseStatus()` on mount. "Regenerate" calls `pulseSetup()` and shows the claim token in a copyable field. "Disconnect" calls `pulseDisconnect()`.

- [ ] **Step 2: Add to Settings.tsx**

Import and add `<PulseSettings />` as a new card in the grid.

- [ ] **Step 3: Verify build**

Run: `cd /Users/proxy/trading/lite/frontend && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PulseSettings.tsx frontend/src/pages/Settings.tsx
git commit -m "feat(pulse): add Lite Pulse settings card with regenerate/disconnect"
```

---

## Phase 3: Android App

### Task 9: Lite Pulse Branding — Theme, Colors, Strings, Icon

**Files (all under `lite-widget/`):**
- Modify: `app/src/main/res/values/colors.xml`
- Modify: `app/src/main/res/values/strings.xml`
- Create: `app/src/main/res/values/themes.xml`
- Create: `app/src/main/res/drawable/ic_launcher_foreground.xml`
- Create: `app/src/main/res/drawable/ic_launcher_background.xml`
- Create: `app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml`
- Create: `app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml`
- Modify: `app/src/main/AndroidManifest.xml` — update theme, app label

- [ ] **Step 1: Update colors.xml with full Lite palette**

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="bg_primary">#1A1A1A</color>
    <color name="bg_secondary">#252525</color>
    <color name="bg_tertiary">#2A2A2A</color>
    <color name="text_primary">#E0E0E0</color>
    <color name="text_secondary">#999999</color>
    <color name="text_muted">#666666</color>
    <color name="border_primary">#363636</color>
    <color name="brand">#A3E635</color>
    <color name="brand_dark">#8BC926</color>
    <color name="positive">#4CAF50</color>
    <color name="negative">#E53935</color>
    <color name="pill_background">#1A1A1A</color>
    <color name="pill_label">#999999</color>
</resources>
```

- [ ] **Step 2: Update strings.xml — rename to Lite Pulse**

- [ ] **Step 3: Create themes.xml — dark theme**

- [ ] **Step 4: Create adaptive icon files**

Vector drawable foreground with the pulse polyline, solid dark background, adaptive icon XML wrappers.

- [ ] **Step 5: Update AndroidManifest.xml — theme + label**

- [ ] **Step 6: Build**

Run: `cd /Users/proxy/trading/lite-widget && ./gradlew assembleDebug 2>&1 | tail -5`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(pulse): rebrand to Lite Pulse with dark theme and custom icon"
```

---

### Task 10: Branded Setup Screen Layout

**Files:**
- Rewrite: `lite-widget/app/src/main/res/layout/activity_main.xml`

- [ ] **Step 1: Rewrite activity_main.xml**

Dark layout with:
1. Header: pulse icon + "Lite Pulse" title + "Floating NIFTY overlay" subtitle
2. Status cards (overlay permission, notification permission, API key) — each in `#252525` rounded cards with `#363636` border
3. Full-width Start/Stop button — brand green / red
4. Battery note — muted 12sp text
5. Collapsible "Enter key manually" section

All text colors, backgrounds, borders match Lite theme from colors.xml.

- [ ] **Step 2: Build and verify**

Run: `cd /Users/proxy/trading/lite-widget && ./gradlew assembleDebug`

- [ ] **Step 3: Commit**

```bash
git add lite-widget/app/src/main/res/layout/activity_main.xml
git commit -m "feat(pulse): dark branded setup screen with status cards"
```

---

### Task 11: URL Scheme + Token Claim in MainActivity

**Files:**
- Modify: `lite-widget/app/src/main/AndroidManifest.xml`
- Rewrite: `lite-widget/app/src/main/java/com/lite/widget/MainActivity.kt`
- Modify: `lite-widget/app/build.gradle.kts`

- [ ] **Step 1: Add URL scheme intent-filter to AndroidManifest.xml**

Add to MainActivity, after the existing LAUNCHER intent-filter:

```xml
<intent-filter>
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="litewidget" android:host="start" />
</intent-filter>
```

- [ ] **Step 2: Update MainActivity.kt**

Handle `intent?.data` in `onCreate`:
- If scheme is `litewidget` and has `token` query param → call `/api/v1/agent/pulse/claim` via OkHttp (already a dependency), store returned API key in SharedPreferences, auto-start service, `finish()`
- If no token but key already saved → auto-start, `finish()`
- Otherwise → show setup screen

The claim HTTP call must be on a background thread (use `Thread { ... }.start()` or coroutine — keep it simple with a thread since we're not adding coroutine deps).

Bind the new dark layout's views. Collapsible manual key section (toggle visibility on tap).

- [ ] **Step 3: Build and verify**

Run: `cd /Users/proxy/trading/lite-widget && ./gradlew assembleDebug`

- [ ] **Step 4: Commit**

```bash
git add lite-widget/
git commit -m "feat(pulse): URL scheme handler with automatic token claim"
```

---

### Task 12: Final Build + Upload APK

- [ ] **Step 1: Full clean build**

Run: `cd /Users/proxy/trading/lite-widget && ./gradlew clean assembleDebug`

- [ ] **Step 2: Upload to Drive and share**

```bash
gog drive upload lite-widget/app/build/outputs/apk/debug/app-debug.apk --name "lite-pulse.apk" --json
gog drive share <fileId> --email anshjain232@gmail.com --role reader --force
```

- [ ] **Step 3: Test on device**

Install, verify branding, test URL scheme launch from PWA, verify token claim flow.
