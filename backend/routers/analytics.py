from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user
from schemas import AnalyticsResponse
from services.analytics_service import analytics_summary


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsResponse)
def analytics(portfolio_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        return analytics_summary(db, portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{portfolio_id}", response_model=AnalyticsResponse, include_in_schema=False)
def analytics_legacy(portfolio_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        return analytics_summary(db, portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
