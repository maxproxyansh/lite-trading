from __future__ import annotations

import time

import httpx
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


# ── Global markets (TradingView scanner API) ─────────────────

_GLOBAL_SYMBOLS = [
    {"ticker": "SP:SPX", "name": "S&P 500", "group": "Indices"},
    {"ticker": "DJ:DJI", "name": "Dow Jones", "group": "Indices"},
    {"ticker": "NASDAQ:IXIC", "name": "Nasdaq Composite", "group": "Indices"},
    {"ticker": "NSE:NIFTY1!", "name": "GIFT Nifty", "group": "Indices"},
    {"ticker": "FX:UKOIL", "name": "Brent Crude", "group": "Commodities"},
    {"ticker": "TVC:GOLD", "name": "Gold", "group": "Commodities"},
    {"ticker": "TVC:US10Y", "name": "US 10Y Yield", "group": "Bonds"},
    {"ticker": "TVC:JP10Y", "name": "Japan 10Y Yield", "group": "Bonds"},
    {"ticker": "TVC:DXY", "name": "Dollar Index", "group": "Forex"},
    {"ticker": "FX_IDC:USDINR", "name": "USD/INR", "group": "Forex"},
]
_GLOBAL_COLUMNS = ["close", "change", "change_abs", "high", "low", "open", "Perf.W", "Perf.1M", "Perf.3M", "Perf.YTD", "price_52_week_high", "price_52_week_low"]
_global_cache: dict = {"data": None, "ts": 0}
_CACHE_TTL = 60


@router.get("/global")
async def global_markets(_actor=Depends(get_current_user_or_agent)):
    now = time.time()
    if _global_cache["data"] and now - _global_cache["ts"] < _CACHE_TTL:
        return _global_cache["data"]

    tickers = [s["ticker"] for s in _GLOBAL_SYMBOLS]
    payload = {"symbols": {"tickers": tickers}, "columns": _GLOBAL_COLUMNS}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post("https://scanner.tradingview.com/global/scan", json=payload)
            resp.raise_for_status()
            raw = resp.json()
    except Exception as exc:
        if _global_cache["data"]:
            return _global_cache["data"]
        raise HTTPException(status_code=503, detail=f"Failed to fetch global markets: {exc}") from exc

    sym_lookup = {s["ticker"]: s for s in _GLOBAL_SYMBOLS}
    result = []
    for row in raw.get("data", []):
        ticker = row.get("s", "")
        vals = row.get("d", [])
        sym = sym_lookup.get(ticker)
        if not sym:
            continue
        close = vals[0] if len(vals) > 0 else None
        change_abs = vals[2] if len(vals) > 2 else None
        prev_close = round(close - change_abs, 4) if close is not None and change_abs is not None else None
        result.append({
            "ticker": sym["ticker"],
            "name": sym["name"],
            "group": sym["group"],
            "close": close,
            "change_pct": vals[1] if len(vals) > 1 else None,
            "change_abs": change_abs,
            "high": vals[3] if len(vals) > 3 else None,
            "low": vals[4] if len(vals) > 4 else None,
            "open": vals[5] if len(vals) > 5 else None,
            "prev_close": prev_close,
            "perf_w": vals[6] if len(vals) > 6 else None,
            "perf_1m": vals[7] if len(vals) > 7 else None,
            "perf_3m": vals[8] if len(vals) > 8 else None,
            "perf_ytd": vals[9] if len(vals) > 9 else None,
            "week52_high": vals[10] if len(vals) > 10 else None,
            "week52_low": vals[11] if len(vals) > 11 else None,
        })

    response = {"quotes": result}
    _global_cache["data"] = response
    _global_cache["ts"] = now
    return response
