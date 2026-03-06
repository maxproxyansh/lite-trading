from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user
from models import Signal
from schemas import SignalResponse


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/signals", tags=["signals"])


@router.get("/latest", response_model=SignalResponse | None)
def latest_signal(db: Session = Depends(get_db), user=Depends(get_current_user)):
    signal = db.query(Signal).order_by(Signal.generated_at.desc()).first()
    return SignalResponse.model_validate(signal) if signal else None


@router.get("", response_model=list[SignalResponse])
def list_signals(limit: int = 50, db: Session = Depends(get_db), user=Depends(get_current_user)):
    signals = db.query(Signal).order_by(Signal.generated_at.desc()).limit(limit).all()
    return [SignalResponse.model_validate(signal) for signal in signals]
