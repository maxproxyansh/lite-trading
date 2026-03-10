from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user, get_user_portfolio_ids
from models import Portfolio
from schemas import OrderRequest, OrderSummary
from services.trading_service import list_orders, place_order


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/orders", tags=["orders"])


@router.get("", response_model=list[OrderSummary])
def get_orders(
    portfolio_id: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    user_portfolio_ids: list[str] = Depends(get_user_portfolio_ids),
):
    if portfolio_id and portfolio_id not in user_portfolio_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    target_id = portfolio_id if portfolio_id else (user_portfolio_ids[0] if user_portfolio_ids else None)
    if not target_id:
        return []
    return [OrderSummary.model_validate(order) for order in list_orders(db, target_id)]


@router.post("", response_model=OrderSummary)
def submit_order(
    payload: OrderRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    user_portfolio_ids: list[str] = Depends(get_user_portfolio_ids),
):
    if payload.portfolio_id not in user_portfolio_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your portfolio")
    order = place_order(db, payload, actor_type="user", actor_id=user.id, source="human")
    return OrderSummary.model_validate(order)
