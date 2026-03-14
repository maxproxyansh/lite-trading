from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from config import get_settings
from dependencies import get_current_user_or_agent
from schemas import CandleResponse, DhanProviderHealth, OptionChainResponse
from services.dhan_credential_service import DhanApiError
from services.market_data import CandleQueryError, market_data_service


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/market", tags=["market"])


@router.get("/snapshot")
def snapshot(_actor=Depends(get_current_user_or_agent)):
    return market_data_service.get_snapshot()


@router.get("/expiries")
def expiries(_actor=Depends(get_current_user_or_agent)):
    return {"expiries": market_data_service.expiries, "active_expiry": market_data_service.active_expiry}


@router.get("/provider-health", response_model=DhanProviderHealth)
def provider_health(_actor=Depends(get_current_user_or_agent)):
    return market_data_service.get_provider_health()


@router.get("/chain", response_model=OptionChainResponse)
async def chain(expiry: str | None = None, _actor=Depends(get_current_user_or_agent)):
    try:
        if expiry and expiry != market_data_service.active_expiry:
            activated = await market_data_service.activate_expiry(expiry)
            if not activated and not market_data_service.option_rows:
                raise HTTPException(status_code=503, detail="OPTION_CHAIN_UNAVAILABLE")
    except DhanApiError as exc:
        raise HTTPException(status_code=503, detail=exc.reason) from exc
    return market_data_service.get_option_chain()


@router.get("/candles", response_model=CandleResponse)
async def candles(
    timeframe: str = "15m",
    before: int | None = None,
    symbol: str | None = None,
    security_id: str | None = None,
    _actor=Depends(get_current_user_or_agent),
):
    try:
        data = await market_data_service.get_candles(timeframe, before=before, symbol=symbol, security_id=security_id)
    except CandleQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return CandleResponse(**data)


@router.get("/depth/{symbol}")
def depth(symbol: str, _actor=Depends(get_current_user_or_agent)):
    depth_data = market_data_service.get_depth(symbol)
    return {"symbol": symbol, "depth": depth_data}
