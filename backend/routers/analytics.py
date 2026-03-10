from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user, get_user_portfolio_ids
from schemas import AnalyticsResponse
from services.analytics_service import analytics_summary


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsResponse)
def analytics(
    portfolio_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    user_portfolio_ids: list[str] = Depends(get_user_portfolio_ids),
):
    if portfolio_id not in user_portfolio_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    try:
        return analytics_summary(db, portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{portfolio_id}", response_model=AnalyticsResponse, include_in_schema=False)
def analytics_legacy(
    portfolio_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    user_portfolio_ids: list[str] = Depends(get_user_portfolio_ids),
):
    if portfolio_id not in user_portfolio_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    try:
        return analytics_summary(db, portfolio_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
