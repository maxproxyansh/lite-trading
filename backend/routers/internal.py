from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import require_dhan_authority_key
from schemas import DhanConsumerStateUpdateRequest, DhanLeaseResponse
from services.dhan_credential_service import DhanApiError, dhan_credential_service
from services.market_data import market_data_service


router = APIRouter(prefix="/internal/dhan", tags=["internal-dhan"])


@router.get("/lease", response_model=DhanLeaseResponse)
def lease(_authority=Depends(require_dhan_authority_key)):
    try:
        snapshot = dhan_credential_service.issue_lease()
    except DhanApiError as exc:
        raise HTTPException(status_code=503, detail=exc.reason) from exc
    return DhanLeaseResponse(
        client_id=snapshot.client_id or "",
        access_token=snapshot.access_token or "",
        expires_at=snapshot.expires_at,
        generation=snapshot.generation,
        validated_at=snapshot.last_profile_checked_at,
        token_source=snapshot.token_source,
        data_plan_status=snapshot.data_plan_status,
        data_valid_until=snapshot.data_valid_until,
    )


@router.post("/consumer-state")
async def consumer_state(
    payload: DhanConsumerStateUpdateRequest,
    _authority=Depends(require_dhan_authority_key),
):
    await market_data_service.record_consumer_state(payload)
    return {"ok": True}
