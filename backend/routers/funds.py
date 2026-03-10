from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user, get_user_portfolio_ids
from schemas import FundsResponse
from services.trading_service import funds_summary


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/funds", tags=["funds"])


@router.get("", response_model=FundsResponse)
def get_funds(
    portfolio_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    user_portfolio_ids: list[str] = Depends(get_user_portfolio_ids),
):
    if portfolio_id not in user_portfolio_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return funds_summary(db, portfolio_id)


@router.get("/{portfolio_id}", response_model=FundsResponse, include_in_schema=False)
def get_funds_legacy(
    portfolio_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    user_portfolio_ids: list[str] = Depends(get_user_portfolio_ids),
):
    if portfolio_id not in user_portfolio_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return funds_summary(db, portfolio_id)
