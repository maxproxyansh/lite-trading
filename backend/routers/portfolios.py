from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user
from models import Portfolio
from schemas import PortfolioSummary
from services.trading_service import portfolio_summary


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/portfolios", tags=["portfolios"])


@router.get("", response_model=list[PortfolioSummary])
def list_portfolios(db: Session = Depends(get_db), user=Depends(get_current_user)):
    portfolios = db.query(Portfolio).order_by(Portfolio.id.asc()).all()
    return [PortfolioSummary(**portfolio_summary(db, portfolio)) for portfolio in portfolios]


@router.get("/{portfolio_id}", response_model=PortfolioSummary)
def get_portfolio(portfolio_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return PortfolioSummary(**portfolio_summary(db, portfolio))
