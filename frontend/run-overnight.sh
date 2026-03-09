#!/usr/bin/env bash
# Overnight autonomous redesign — bulletproof version
# NO set -e. Errors are logged, never fatal.

WORK_DIR="/Users/proxy/trading/lite/frontend"
LOG_DIR="$WORK_DIR/.claude/logs"
TASK_FILE="$WORK_DIR/.claude/overnight-tasks.md"
MAX_ITERATIONS=20

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_DIR/runner.log"
}

slack_notify() {
  openclaw message send --channel slack --target "#general" --message "$1" 2>/dev/null || true
}

run_phase() {
  local iteration="$1"
  local prompt="$2"
  local log_file="$LOG_DIR/iteration-$(printf '%02d' "$iteration").log"

  log "=== ITERATION $iteration ==="

  # Run claude, capture output. Never fail the script.
  echo "$prompt" | claude --dangerously-skip-permissions -p > "$log_file" 2>&1
  local exit_code=$?

  log "Iteration $iteration finished (exit=$exit_code). Log: $log_file"

  if [ $exit_code -ne 0 ]; then
    log "WARNING: claude exited non-zero ($exit_code), continuing anyway"
    slack_notify "⚠️ Lite overnight: iteration $iteration exited with code $exit_code. Continuing to next phase."
  fi

  # Brief pause between iterations
  sleep 5
  return 0
}

# Unset CLAUDECODE to allow launching from within another claude session
unset CLAUDECODE

cd "$WORK_DIR" || exit 1

log "=========================================="
log "Starting overnight redesign pipeline v2"
log "=========================================="
slack_notify "🚀 Lite overnight redesign started. $MAX_ITERATIONS iterations planned. Will notify on completion or errors."

# ── PHASE 1: CSS + Login ──
run_phase 1 "$(cat <<'PROMPT'
Read /Users/proxy/trading/lite/frontend/.claude/overnight-tasks.md AND /Users/proxy/trading/lite/frontend/CLAUDE.md for the full design spec.

CRITICAL: Kite dark mode is NEUTRAL CHARCOAL gray, NOT navy. Background colors must be #1a1a1a, #252525, #2a2a2a — pure grays with ZERO blue tint. Check globals.css and fix if needed.

PHASE 1: Foundation — verify CSS theme and login page.

1. Read src/styles/globals.css — verify ALL @theme colors are neutral charcoal (no navy/blue hex codes like #1b1b2f). Fix any wrong colors.
2. Read index.html — verify Lato font is loaded from Google Fonts. Fix if missing.
3. Read and improve src/pages/Login.tsx — sharp corners (rounded-sm), clean inputs with proper padding, blue login button.
4. Run `npm run build` — must have ZERO errors
5. Deploy: `cd /Users/proxy/trading/lite/frontend && npx vercel --prod --yes`
6. Screenshot: `playwright screenshot --wait-for-timeout 3000 --viewport-size=1440,900 "https://litetrade.vercel.app" /tmp/phase1.png`
7. View screenshot to confirm neutral dark gray (NOT navy) background
PROMPT
)"

# ── PHASE 2: Header + Sidebar ──
run_phase 2 "$(cat <<'PROMPT'
Read /Users/proxy/trading/lite/frontend/.claude/overnight-tasks.md AND /Users/proxy/trading/lite/frontend/CLAUDE.md for the full design spec.

PHASE 2: Header and MarketWatch — must look EXACTLY like Zerodha Kite.

1. Read src/components/Header.tsx and REWRITE it to match Kite exactly:
   - 48px height, dark charcoal background (#1a1a1a), bottom border
   - LEFT: "NIFTY 50" label + spot price (green/red) + change% | "SENSEX" same pattern
   - CENTER: Kite red logo/icon, then nav tabs: Dashboard, Orders, Holdings, Positions, Funds, Analytics
   - Active tab: blue text + 2px blue bottom border. Others: gray
   - RIGHT: green/red WS dot, portfolio dropdown, user avatar circle, logout icon
   - Font: 13px Lato. No rounded corners.

2. Read src/components/MarketWatch.tsx and REWRITE to match Kite watchlist:
   - 300px sidebar, search with ⌘K badge
   - "Options (N)" count + market status dot
   - Scrollable list, CE=green PE=red, B/S buttons on hover
   - Selected row highlighted

3. Build, deploy, screenshot, verify. Colors must be charcoal gray NOT navy.
PROMPT
)"

# ── PHASE 3: Dashboard ──
run_phase 3 "$(cat <<'PROMPT'
Read /Users/proxy/trading/lite/frontend/.claude/overnight-tasks.md AND /Users/proxy/trading/lite/frontend/CLAUDE.md.

PHASE 3: Dashboard — chart, options chain, right panel.

1. Read and improve src/pages/Dashboard.tsx — clean three-panel layout
2. Read and improve src/components/NiftyChart.tsx — chart with charcoal colors (#1a1a1a bg, #2e2e2e grid, #363636 borders). Timeframe pills sharp (rounded-sm).
3. Read and improve src/components/OptionsChain.tsx — sticky header, CE green/PE red, ATM highlight, expiry selector
4. Read and improve src/components/OrderTicket.tsx — clean order form, BUY green/SELL red buttons
5. Read and improve src/components/SignalPanel.tsx — agent signal display
6. Build, deploy, screenshot, verify. ALL hardcoded colors must be neutral gray not navy.
PROMPT
)"

# ── PHASE 4: All pages ──
run_phase 4 "$(cat <<'PROMPT'
Read /Users/proxy/trading/lite/frontend/.claude/overnight-tasks.md AND /Users/proxy/trading/lite/frontend/CLAUDE.md.

PHASE 4: Fix ALL secondary pages.

1. Read and fix src/pages/Orders.tsx — clean table, BUY green/SELL red, proper empty state
2. Read and fix src/pages/Positions.tsx — P&L colored, Exit button, count in header
3. Read and fix src/pages/History.tsx — tradebook table, consistent with Orders
4. Read and fix src/pages/Funds.tsx — Kite-style "Hi, Name" + equity/P&L two-column layout
5. Read and fix src/pages/Analytics.tsx — FIX broken rendering. Stat cards, charts. Handle empty data gracefully. ALL chart hardcoded colors must be neutral gray (#1a1a1a, #2e2e2e, #363636, #666666).
6. Read and fix src/pages/Settings.tsx — clean cards
7. Build, deploy, screenshot, verify
PROMPT
)"

# ── PHASE 5: Polish ──
run_phase 5 "$(cat <<'PROMPT'
Read /Users/proxy/trading/lite/frontend/.claude/overnight-tasks.md AND /Users/proxy/trading/lite/frontend/CLAUDE.md.

PHASE 5: Polish — ticker bar, toasts, loading states, overall consistency.

1. Read and improve src/components/TickerBar.tsx — bottom scrolling ticker
2. Read and improve src/components/Toast.tsx — bottom-right, auto-dismiss
3. Read and improve src/components/LoadingState.tsx — blue spinner, clean empty states
4. Read src/App.tsx — verify layout is correct, no overflow issues
5. Grep the ENTIRE src/ directory for any remaining navy/blue hex codes (#1a1a2e, #1b1b2f, #232341, #2d2d4a, #323253, #2a2a44, #2a2a46, #5e5e76, #333350, #434360, #e8e8ee, #9b9bad, #5a5a72). Replace ALL with neutral grays.
6. Build, deploy, screenshot, verify
PROMPT
)"

# ── PHASES 6-20: Iterative improvement ──
for i in $(seq 6 "$MAX_ITERATIONS"); do
  run_phase "$i" "$(cat <<'PROMPT'
Read /Users/proxy/trading/lite/frontend/.claude/overnight-tasks.md AND /Users/proxy/trading/lite/frontend/CLAUDE.md.

ITERATIVE IMPROVEMENT PASS.

1. Run: cd /Users/proxy/trading/lite/frontend && npx vercel --prod --yes
2. Screenshot login: playwright screenshot --wait-for-timeout 3000 --viewport-size=1440,900 "https://litetrade.vercel.app/login" /tmp/review-login.png
3. View the screenshot. Is the background neutral dark charcoal gray (like #1a1a1a)? Or does it have a blue/navy tint? If blue tint, fix globals.css immediately.
4. Grep src/ for any remaining wrong hex codes. Fix them all.
5. Identify the TOP 3 visual issues vs Kite dark mode and fix them:
   - Does header look like Kite? (market data left, red logo center, nav tabs, user right)
   - Is sidebar exactly like Kite watchlist?
   - Are tables clean and professional?
   - Are all colors neutral charcoal gray with no blue tint?
   - Are corners sharp (not rounded)?
   - Is font Lato?
6. After fixes, build, deploy, screenshot again, verify improvement.
7. If everything looks great, add micro-improvements: hover states, transitions, better empty states.
PROMPT
)"
done

log "=========================================="
log "ALL $MAX_ITERATIONS ITERATIONS COMPLETE"
log "=========================================="
slack_notify "✅ Lite overnight redesign COMPLETE. All $MAX_ITERATIONS iterations finished. Check https://litetrade.vercel.app"
