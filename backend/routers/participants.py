from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from config import get_settings
from dependencies import get_current_user_or_agent
from schemas import ParticipantHistoryResponse, ParticipantPositions, ParticipantSnapshot
from services import participant_service

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{settings.api_prefix}/participants", tags=["participants"])


def _to_schema(raw: dict) -> ParticipantSnapshot:
    return ParticipantSnapshot(
        date=raw["date"],
        fii=ParticipantPositions(**raw["fii"]),
        dii=ParticipantPositions(**raw["dii"]),
        pro=ParticipantPositions(**raw["pro"]),
        client=ParticipantPositions(**raw["client"]),
    )


@router.get("/today", response_model=ParticipantSnapshot)
def get_today(user=Depends(get_current_user_or_agent)):
    data = participant_service.get_latest()
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Participant data not available from NSE",
        )
    return _to_schema(data)


@router.get("/history", response_model=ParticipantHistoryResponse)
def get_history(
    days: int = Query(default=30, ge=1, le=90),
    user=Depends(get_current_user_or_agent),
):
    snapshots = participant_service.get_history(days)
    return ParticipantHistoryResponse(
        snapshots=[_to_schema(s) for s in snapshots],
    )
