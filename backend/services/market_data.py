from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from dhanhq import dhanhq as Dhanhq

from config import get_settings
from market_hours import market_status
from schemas import MarketSnapshot, OptionChainResponse


settings = get_settings()

BroadcastFn = Callable[[str, dict[str, Any]], Awaitable[None]]
ProcessOrdersFn = Callable[[], Awaitable[None]]


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class MarketDataService:
    def __init__(self) -> None:
        self._broadcast: BroadcastFn | None = None
        self._process_orders: ProcessOrdersFn | None = None
        self.expiries: list[str] = []
        self.active_expiry: str | None = None
        self.snapshot: dict[str, Any] = {
            "spot_symbol": "NIFTY 50",
            "spot": 0.0,
            "change": 0.0,
            "change_pct": 0.0,
            "vix": None,
            "pcr": None,
            "market_status": market_status(),
            "expiries": [],
            "active_expiry": None,
            "degraded": True,
            "degraded_reason": "INITIALIZING",
            "updated_at": datetime.now(timezone.utc),
        }
        self.option_rows: list[dict[str, Any]] = []
        self.quotes: dict[str, dict[str, Any]] = {}
        self.last_expiry_refresh: datetime | None = None
        self.last_vix_refresh: datetime | None = None
        self.last_known_spot: float = 0.0
        self.last_known_prev_close: float = 0.0
        self.last_known_change: float = 0.0
        self.last_known_change_pct: float = 0.0
        self._task: asyncio.Task | None = None

    def set_broadcast(self, broadcast: BroadcastFn) -> None:
        self._broadcast = broadcast

    def set_open_order_processor(self, processor: ProcessOrdersFn) -> None:
        self._process_orders = processor

    def _has_dhan(self) -> bool:
        return bool(settings.dhan_client_id and settings.dhan_access_token)

    def _client(self) -> Dhanhq:
        return Dhanhq(settings.dhan_client_id, settings.dhan_access_token)

    async def start(self) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self.refresh()
                if self._process_orders:
                    await self._process_orders()
            except Exception:  # noqa: BLE001
                self.snapshot["degraded"] = True
                self.snapshot["degraded_reason"] = "MARKET_REFRESH_FAILED"
                self.snapshot["updated_at"] = datetime.now(timezone.utc)
            await asyncio.sleep(settings.market_poll_seconds)

    async def refresh(self) -> None:
        if not self._has_dhan():
            self.snapshot["degraded"] = True
            self.snapshot["degraded_reason"] = "DHAN_NOT_CONFIGURED"
            self.snapshot["updated_at"] = datetime.now(timezone.utc)
            await self._broadcast_snapshot()
            return

        now = datetime.now(timezone.utc)
        if not self.last_expiry_refresh or now - self.last_expiry_refresh > timedelta(minutes=10):
            self.expiries = await asyncio.to_thread(self._fetch_expiries)
            self.last_expiry_refresh = now
            if self.expiries and self.active_expiry not in self.expiries:
                self.active_expiry = self.expiries[0]

        # Auto-advance if active expiry is in the past
        if self.active_expiry:
            try:
                expiry_date = datetime.strptime(self.active_expiry, "%Y-%m-%d").date()
                if expiry_date < date.today() and self.expiries:
                    future = [e for e in self.expiries if e >= date.today().isoformat()]
                    if future:
                        self.active_expiry = future[0]
                    elif self.expiries:
                        self.active_expiry = self.expiries[0]
            except ValueError:
                pass

        if not self.active_expiry:
            self.snapshot["degraded"] = True
            self.snapshot["degraded_reason"] = "NO_EXPIRIES"
            self.snapshot["updated_at"] = now
            await self._broadcast_snapshot()
            return

        chain = await asyncio.to_thread(self._fetch_option_chain, self.active_expiry)
        if not chain:
            self.snapshot["degraded"] = True
            self.snapshot["degraded_reason"] = "OPTION_CHAIN_UNAVAILABLE"
            self.snapshot["updated_at"] = now
            await self._broadcast_snapshot()
            return

        self.option_rows = chain["rows"]
        self.quotes = chain["quotes"]
        self.snapshot.update(chain["snapshot"])
        self.snapshot["expiries"] = self.expiries
        self.snapshot["active_expiry"] = self.active_expiry
        self.snapshot["market_status"] = market_status()
        self.snapshot["degraded"] = False
        self.snapshot["degraded_reason"] = None
        self.snapshot["updated_at"] = now

        if not self.last_vix_refresh or now - self.last_vix_refresh > timedelta(minutes=5):
            vix = await asyncio.to_thread(self._fetch_vix)
            if vix is not None:
                self.snapshot["vix"] = vix
            self.last_vix_refresh = now

        await self._broadcast_snapshot()
        await self._broadcast_chain()

    async def _broadcast_snapshot(self) -> None:
        if self._broadcast:
            await self._broadcast("market.snapshot", self.get_snapshot().model_dump(mode="json"))

    async def _broadcast_chain(self) -> None:
        if self._broadcast:
            response = self.get_option_chain(self.active_expiry)
            await self._broadcast("option.chain", response.model_dump(mode="json"))

    def set_active_expiry(self, expiry: str) -> None:
        self.active_expiry = expiry

    def get_snapshot(self) -> MarketSnapshot:
        return MarketSnapshot(**self.snapshot)

    def get_option_chain(self, expiry: str | None = None) -> OptionChainResponse:
        if expiry and expiry != self.active_expiry:
            self.active_expiry = expiry
        return OptionChainResponse(snapshot=self.get_snapshot(), rows=self.option_rows)

    def get_quote(self, symbol: str) -> dict[str, Any] | None:
        return self.quotes.get(symbol)

    def resolve_symbol(self, *, expiry: str, strike: int, option_type: str) -> str:
        return f"NIFTY_{expiry}_{strike}_{option_type.upper()}"

    def get_depth(self, symbol: str) -> dict[str, Any] | None:
        return self.quotes.get(symbol)

    def _fetch_expiries(self) -> list[str]:
        try:
            result = self._client().expiry_list(under_security_id=13, under_exchange_segment="IDX_I")
            payload = result.get("data", {}) if isinstance(result, dict) else {}
            raw = payload.get("data", []) if isinstance(payload, dict) else []
            return [str(item) for item in raw if item]
        except Exception:  # noqa: BLE001
            return []

    def _fetch_vix(self) -> float | None:
        try:
            today = date.today()
            from_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
            to_date = today.strftime("%Y-%m-%d")
            result = self._client().historical_daily_data(
                security_id="21",
                exchange_segment="IDX_I",
                instrument_type="INDEX",
                from_date=from_date,
                to_date=to_date,
            )
            payload = result.get("data", {}) if isinstance(result, dict) else {}
            closes = payload.get("close", []) if isinstance(payload, dict) else []
            return float(closes[-1]) if closes else None
        except Exception:  # noqa: BLE001
            return None

    def _fetch_option_chain(self, expiry: str) -> dict[str, Any] | None:
        try:
            response = self._client().option_chain(under_security_id=13, under_exchange_segment="IDX_I", expiry=expiry)
        except Exception:  # noqa: BLE001
            return None

        body = response.get("data", {}) if isinstance(response, dict) else {}
        if isinstance(body, dict) and "data" in body:
            body = body["data"]
        if not isinstance(body, dict):
            return None

        raw_map = body.get("oc", {}) or {}
        if not raw_map:
            return None

        quotes: dict[str, dict[str, Any]] = {}
        rows: list[dict[str, Any]] = []
        spot = float(body.get("last_price") or 0.0)
        prev_close = float(body.get("prev_close") or body.get("previous_close") or 0.0)

        if spot > 0:
            self.last_known_spot = spot
        if prev_close > 0:
            self.last_known_prev_close = prev_close

        effective_spot = spot if spot > 0 else self.last_known_spot
        effective_prev = prev_close if prev_close > 0 else self.last_known_prev_close

        atm = round(effective_spot / 50) * 50 if effective_spot else None

        change = round(effective_spot - effective_prev, 2) if effective_prev else self.last_known_change
        change_pct = round((change / effective_prev) * 100, 2) if effective_prev else self.last_known_change_pct

        if effective_spot > 0:
            self.last_known_change = change
            self.last_known_change_pct = change_pct

        strike_range = 2000
        total_call_oi = 0.0
        total_put_oi = 0.0

        for strike_key in sorted(raw_map.keys(), key=lambda item: float(item)):
            try:
                strike = int(float(strike_key))
            except (TypeError, ValueError):
                continue
            if atm and abs(strike - atm) > strike_range:
                continue
            option_data = raw_map[strike_key] or {}
            call = self._map_option_quote(option_data.get("ce", {}) or {}, expiry, strike, "CE")
            put = self._map_option_quote(option_data.get("pe", {}) or {}, expiry, strike, "PE")
            quotes[call["symbol"]] = call
            quotes[put["symbol"]] = put
            total_call_oi += float(call.get("oi") or 0.0)
            total_put_oi += float(put.get("oi") or 0.0)
            rows.append(
                {
                    "strike": strike,
                    "is_atm": atm == strike,
                    "call": call,
                    "put": put,
                }
            )

        pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else None
        return {
            "quotes": quotes,
            "rows": rows,
            "snapshot": {
                "spot_symbol": "NIFTY 50",
                "spot": effective_spot,
                "change": change,
                "change_pct": change_pct,
                "vix": self.snapshot.get("vix"),
                "pcr": pcr,
                "market_status": market_status(),
                "expiries": self.expiries,
                "active_expiry": expiry,
                "degraded": False,
                "degraded_reason": None,
                "updated_at": datetime.now(timezone.utc),
            },
        }

    def _map_option_quote(self, payload: dict[str, Any], expiry: str, strike: int, option_type: str) -> dict[str, Any]:
        best_bid = (
            payload.get("best_bid_price")
            or payload.get("top_bid_price")
            or payload.get("bid")
            or payload.get("bestBidPrice")
            or payload.get("topBidPrice")
        )
        best_ask = (
            payload.get("best_ask_price")
            or payload.get("top_ask_price")
            or payload.get("ask")
            or payload.get("bestAskPrice")
            or payload.get("topAskPrice")
        )
        bid_qty = (
            payload.get("best_bid_qty")
            or payload.get("top_bid_quantity")
            or payload.get("bestBidQty")
            or payload.get("topBidQuantity")
        )
        ask_qty = (
            payload.get("best_ask_qty")
            or payload.get("top_ask_quantity")
            or payload.get("bestAskQty")
            or payload.get("topAskQuantity")
        )
        greeks = payload.get("greeks", {}) or {}
        symbol = self.resolve_symbol(expiry=expiry, strike=strike, option_type=option_type)
        raw_oi = self._safe_float(payload.get("oi") or payload.get("open_interest"))
        return {
            "symbol": symbol,
            "security_id": self._extract_security_id(payload),
            "strike": strike,
            "option_type": option_type,
            "expiry": expiry,
            "ltp": float(payload.get("last_price") or payload.get("ltp") or 0.0),
            "bid": float(best_bid) if best_bid is not None else None,
            "ask": float(best_ask) if best_ask is not None else None,
            "bid_qty": int(bid_qty) if bid_qty else None,
            "ask_qty": int(ask_qty) if ask_qty else None,
            "iv": self._safe_float(payload.get("implied_volatility") or payload.get("iv")),
            "oi": raw_oi,
            "oi_lakhs": round(raw_oi / 100000, 2) if raw_oi else None,
            "volume": self._safe_float(payload.get("volume") or payload.get("traded_volume")),
            "delta": self._safe_float(greeks.get("delta")),
            "gamma": self._safe_float(greeks.get("gamma")),
            "theta": self._safe_float(greeks.get("theta")),
            "vega": self._safe_float(greeks.get("vega")),
        }

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_security_id(payload: dict[str, Any]) -> str | None:
        for key in ("security_id", "securityId", "drv_security_id", "drvSecurityId", "instrument_id", "id"):
            if payload.get(key):
                return str(payload[key])
        return None

    async def get_candles(self, timeframe: str) -> dict[str, Any]:
        if not self._has_dhan():
            return {"timeframe": timeframe, "candles": [], "source": "none", "degraded": True}

        try:
            return await asyncio.to_thread(self._fetch_candles, timeframe)
        except Exception:  # noqa: BLE001
            return {"timeframe": timeframe, "candles": [], "source": "dhan", "degraded": True}

    def _fetch_candles(self, timeframe: str) -> dict[str, Any]:
        client = self._client()
        today = date.today()
        if timeframe == "D":
            result = client.historical_daily_data(
                security_id="13",
                exchange_segment="IDX_I",
                instrument_type="INDEX",
                from_date=(today - timedelta(days=90)).strftime("%Y-%m-%d"),
                to_date=today.strftime("%Y-%m-%d"),
            )
            payload = result.get("data", {}) if isinstance(result, dict) else {}
            candles = self._map_candles(payload)
            return {"timeframe": timeframe, "candles": candles[-90:], "source": "dhan", "degraded": False}

        interval_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}
        interval = interval_map.get(timeframe, 15)
        result = client.intraday_minute_data(
            security_id="13",
            exchange_segment="IDX_I",
            instrument_type="INDEX",
            from_date=(today - timedelta(days=5)).strftime("%Y-%m-%d"),
            to_date=today.strftime("%Y-%m-%d"),
            interval=interval,
        )
        payload = result.get("data", {}) if isinstance(result, dict) else {}
        candles = self._map_candles(payload)
        return {"timeframe": timeframe, "candles": candles[-390:], "source": "dhan", "degraded": False}

    def _map_candles(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        timestamps = payload.get("timestamp") or payload.get("start_Time") or payload.get("start_time") or []
        opens = payload.get("open") or []
        highs = payload.get("high") or []
        lows = payload.get("low") or []
        closes = payload.get("close") or []
        volumes = payload.get("volume") or [0] * len(closes)
        candles: list[dict[str, Any]] = []
        for idx, close in enumerate(closes):
            if close is None:
                continue
            ts = timestamps[idx] if idx < len(timestamps) else None
            dt = _parse_datetime(ts)
            candles.append(
                {
                    "time": int(dt.timestamp()),
                    "open": float(opens[idx] if idx < len(opens) and opens[idx] is not None else close),
                    "high": float(highs[idx] if idx < len(highs) and highs[idx] is not None else close),
                    "low": float(lows[idx] if idx < len(lows) and lows[idx] is not None else close),
                    "close": float(close),
                    "volume": float(volumes[idx] if idx < len(volumes) and volumes[idx] is not None else 0),
                }
            )
        return candles


market_data_service = MarketDataService()
