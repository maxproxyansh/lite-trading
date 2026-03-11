from __future__ import annotations

from fastapi import APIRouter, Depends

from config import get_settings
from dependencies import get_current_user
from schemas import CandleResponse, OptionChainResponse
from services.market_data import market_data_service


settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/market", tags=["market"])


@router.get("/snapshot")
def snapshot(user=Depends(get_current_user)):
    return market_data_service.get_snapshot()


@router.get("/expiries")
def expiries(user=Depends(get_current_user)):
    return {"expiries": market_data_service.expiries, "active_expiry": market_data_service.active_expiry}


@router.get("/chain", response_model=OptionChainResponse)
async def chain(expiry: str | None = None, user=Depends(get_current_user)):
    if expiry and expiry != market_data_service.active_expiry:
        market_data_service.set_active_expiry(expiry)
        await market_data_service.refresh()
    return market_data_service.get_option_chain(expiry)


@router.get("/candles", response_model=CandleResponse)
async def candles(timeframe: str = "15m", user=Depends(get_current_user)):
    data = await market_data_service.get_candles(timeframe)
    return CandleResponse(**data)


@router.get("/depth/{symbol}")
def depth(symbol: str, user=Depends(get_current_user)):
    depth_data = market_data_service.get_depth(symbol)
    return {"symbol": symbol, "depth": depth_data}


