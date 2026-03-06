from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user
from schemas import OrderRequest, OrderSummary
from services.trading_service import list_orders, place_order


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/orders", tags=["orders"])


@router.get("", response_model=list[OrderSummary])
def get_orders(portfolio_id: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [OrderSummary.model_validate(order) for order in list_orders(db, portfolio_id)]


@router.post("", response_model=OrderSummary)
def submit_order(payload: OrderRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    order = place_order(db, payload, actor_type="user", actor_id=user.id, source="human")
    return OrderSummary.model_validate(order)
