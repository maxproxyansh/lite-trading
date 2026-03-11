# Lite Options Terminal

Virtual NIFTY options trading platform — Zerodha Kite dark mode clone.

## Architecture
- **Frontend**: React 19 + Vite 7 + Tailwind v4, deployed on Vercel (auto-deploy from `main`)
- **Backend**: FastAPI + SQLAlchemy, deployed on Railway (auto-deploy from `main`, root dir `/backend`)
- **URLs**: Frontend https://litetrade.vercel.app, Backend https://lite-options-api-production.up.railway.app

## Testing

**NEVER create new test accounts.** Use the bootstrap admin account for all testing:
- Credentials are set via Railway env vars: `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`
- The backend auto-creates this account on startup (`auth_service.py:ensure_bootstrap_state()`)
- Check Railway dashboard or `backend/.env` for the actual values
- Public signup MUST stay enabled for real users — do not disable it

## Key Rules
- Frontend CLAUDE.md is at `frontend/CLAUDE.md` — read it for design rules
- Color palette is NEUTRAL CHARCOAL (no blue/navy tint) — see frontend CLAUDE.md
- NIFTY lot size: 65 (centralized in backend config + frontend OrderModal)
- Font: Lato via Google Fonts
- NO pre-filled login credentials in the UI
- NO rounded corners (sharp/angular like Kite, rounded-sm = 2px max)

## Deploy
```bash
# Frontend (auto-deploys on push, or manual)
cd frontend && npx vercel --prod --yes

# Backend (auto-deploys on push to main)
# Manual: cd backend && railway up --detach
```

## Build & Test
```bash
# Frontend
cd frontend && npm run build

# Backend
cd backend && python3 -m pytest tests/test_app.py -q
```
