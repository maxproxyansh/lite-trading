from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from dependencies import get_current_user
from schemas import AlertCreateRequest, AlertSummary
from services.alert_service import cancel_alert, create_alert, list_alerts


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertSummary])
def get_alerts(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [AlertSummary.model_validate(alert) for alert in list_alerts(db, user_id=user.id)]


@router.post("", response_model=AlertSummary, status_code=status.HTTP_201_CREATED)
def post_alert(payload: AlertCreateRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    alert = create_alert(db, user_id=user.id, payload=payload)
    return AlertSummary.model_validate(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(alert_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cancel_alert(db, user_id=user.id, alert_id=alert_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
