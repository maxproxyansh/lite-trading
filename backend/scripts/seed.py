from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from database import SessionLocal, init_db  # noqa: E402
from services.auth_service import ensure_bootstrap_state  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = ensure_bootstrap_state(db)
    finally:
        db.close()
    if user:
        print(f"Seed complete: bootstrap operator ensured for {user.email}.")
    else:
        print("Seed skipped: bootstrap credentials are not configured in backend/.env.")


if __name__ == "__main__":
    main()
