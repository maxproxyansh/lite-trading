from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from dhanhq import dhanhq as Dhanhq
from dhanhq.marketfeed import DhanFeed, Full, IDX, NSE_FNO, Quote

from config import get_settings
from market_hours import IST, market_status
from schemas import MarketSnapshot, OptionChainResponse


settings = get_settings()

NIFTY_INDEX_SECURITY_ID = "13"
VIX_INDEX_SECURITY_ID = "21"
INDEX_EXCHANGE_SEGMENT = "IDX_I"
INDEX_INSTRUMENT_TYPE = "INDEX"
OLDEST_DAILY_HISTORY = date(1990, 1, 1)
MAX_INTRADAY_HISTORY_DAYS = 365 * 5
INITIAL_HISTORY_WINDOWS = {
    "1m": 30,
    "5m": 90,
    "15m": 90,
    "1h": 90,
    "D": 365,
}
INTRADAY_INTERVALS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}

BroadcastFn = Callable[[str, dict[str, Any]], Awaitable[None]]
ProcessOrdersFn = Callable[[set[str]], Awaitable[None]]


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
        self._snapshot_task: asyncio.Task | None = None
        self._feed_task: asyncio.Task | None = None
        self._flush_task: asyncio.Task | None = None
        self._feed: DhanFeed | None = None
        self._desired_feed_instruments: set[tuple[int, str, int]] = set()
        self._subscribed_feed_instruments: set[tuple[int, str, int]] = set()
        self._security_id_to_symbol: dict[str, str] = {}
        self._dirty_quote_symbols: set[str] = set()
        self._snapshot_dirty = False
        self._pcr_dirty = False

    def set_broadcast(self, broadcast: BroadcastFn) -> None:
        self._broadcast = broadcast

    def set_open_order_processor(self, processor: ProcessOrdersFn) -> None:
        self._process_orders = processor

    def _has_dhan(self) -> bool:
        return bool(settings.dhan_client_id and settings.dhan_access_token)

    def _client(self) -> Dhanhq:
        return Dhanhq(settings.dhan_client_id, settings.dhan_access_token)

    @staticmethod
    def _history_anchor(before: int | None) -> datetime:
        if before is None:
            return datetime.now(IST)
        return datetime.fromtimestamp(before, timezone.utc).astimezone(IST)

    def _history_window(self, timeframe: str, before: int | None) -> tuple[date, date, date]:
        anchor = self._history_anchor(before)
        upper_date = anchor.date()
        oldest_date = OLDEST_DAILY_HISTORY if timeframe == "D" else upper_date - timedelta(days=MAX_INTRADAY_HISTORY_DAYS)
        span_days = INITIAL_HISTORY_WINDOWS.get(timeframe, INITIAL_HISTORY_WINDOWS["15m"])
        lower_date = max(oldest_date, upper_date - timedelta(days=max(span_days - 1, 0)))
        return lower_date, upper_date, oldest_date

    @staticmethod
    def _filter_history_before(candles: list[dict[str, Any]], before: int | None) -> list[dict[str, Any]]:
        if before is None:
            return candles
        return [candle for candle in candles if candle["time"] < before]

    @staticmethod
    def _next_history_cursor(
        candles: list[dict[str, Any]],
        *,
        lower_date: date,
        oldest_date: date,
        has_more: bool,
    ) -> int | None:
        if not has_more:
            return None
        if candles:
            return int(candles[0]["time"])
        lower_bound = datetime.combine(lower_date, datetime.min.time(), tzinfo=IST)
        oldest_bound = datetime.combine(oldest_date, datetime.min.time(), tzinfo=IST)
        return int(max(lower_bound, oldest_bound).timestamp())

    async def start(self) -> None:
        if self._snapshot_task or self._feed_task or self._flush_task:
            return
        await self.refresh()
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        self._feed_task = asyncio.create_task(self._feed_loop())
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        for task_name in ("_snapshot_task", "_feed_task", "_flush_task"):
            task = getattr(self, task_name)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                setattr(self, task_name, None)
        await self._reset_feed()

    async def _snapshot_loop(self) -> None:
        interval = max(settings.option_chain_refresh_seconds, 1)
        while True:
            try:
                await self.refresh()
            except Exception:  # noqa: BLE001
                self.snapshot["degraded"] = True
                self.snapshot["degraded_reason"] = "MARKET_REFRESH_FAILED"
                self.snapshot["updated_at"] = datetime.now(timezone.utc)
                self._snapshot_dirty = True
            await asyncio.sleep(interval)

    async def _flush_loop(self) -> None:
        interval = max(settings.market_feed_flush_ms, 50) / 1000
        while True:
            await asyncio.sleep(interval)
            if self._pcr_dirty:
                self.snapshot["pcr"] = self._compute_pcr()
                self.snapshot["updated_at"] = datetime.now(timezone.utc)
                self._pcr_dirty = False
                self._snapshot_dirty = True

            dirty_symbols: tuple[str, ...] = ()
            if self._dirty_quote_symbols:
                dirty_symbols = tuple(self._dirty_quote_symbols)
                self._dirty_quote_symbols = set()
            snapshot_dirty = self._snapshot_dirty
            if not dirty_symbols and not snapshot_dirty:
                continue

            if snapshot_dirty:
                await self._broadcast_snapshot()
                self._snapshot_dirty = False

            if dirty_symbols:
                if self._broadcast:
                    await self._broadcast("option.quotes", self._build_quote_batch(dirty_symbols))
                if self._process_orders:
                    await self._process_orders(set(dirty_symbols))

    async def _feed_loop(self) -> None:
        reconnect_delay = max(settings.market_feed_reconnect_seconds, 1)
        while True:
            try:
                if not self._has_dhan():
                    await asyncio.sleep(reconnect_delay)
                    continue
                if not self._desired_feed_instruments:
                    await asyncio.sleep(0.25)
                    continue
                if not self._feed or not self._feed.ws or self._feed.ws.closed:
                    await self._connect_feed()
                await self._sync_feed_subscriptions()
                try:
                    # dhanhq exposes get_instrument_data() as an async recv wrapper; wait_for prevents a stuck socket.
                    payload = await asyncio.wait_for(self._feed.get_instrument_data(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue
                if payload:
                    self._handle_feed_packet(payload)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                self.snapshot["degraded"] = True
                self.snapshot["degraded_reason"] = "MARKET_FEED_DISCONNECTED"
                self.snapshot["updated_at"] = datetime.now(timezone.utc)
                self._snapshot_dirty = True
                await self._reset_feed()
                await asyncio.sleep(reconnect_delay)

    async def _connect_feed(self) -> None:
        instruments = self._sorted_instruments(self._desired_feed_instruments)
        self._feed = DhanFeed(
            settings.dhan_client_id,
            settings.dhan_access_token,
            instruments,
            version="v2",
        )
        await self._feed.connect()
        self._subscribed_feed_instruments = set(instruments)

    async def _sync_feed_subscriptions(self) -> None:
        if not self._feed:
            return
        desired = set(self._desired_feed_instruments)
        to_add = desired - self._subscribed_feed_instruments
        to_remove = self._subscribed_feed_instruments - desired
        if to_remove:
            self._feed.unsubscribe_symbols(self._sorted_instruments(to_remove))
        if to_add:
            self._feed.subscribe_symbols(self._sorted_instruments(to_add))
        self._subscribed_feed_instruments = desired

    async def _reset_feed(self) -> None:
        if self._feed and self._feed.ws and not self._feed.ws.closed:
            try:
                await self._feed.ws.close()
            except Exception:  # noqa: BLE001
                pass
        self._feed = None
        self._subscribed_feed_instruments.clear()

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

        if self.active_expiry:
            try:
                expiry_date = datetime.strptime(self.active_expiry, "%Y-%m-%d").date()
                if expiry_date < date.today() and self.expiries:
                    future = [expiry for expiry in self.expiries if expiry >= date.today().isoformat()]
                    if future:
                        self.active_expiry = future[0]
                    else:
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
        self._security_id_to_symbol = chain["security_id_to_symbol"]
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

        self._desired_feed_instruments = self._build_feed_instruments()
        self._dirty_quote_symbols.clear()
        self._pcr_dirty = False
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
            result = self._client().expiry_list(
                under_security_id=int(NIFTY_INDEX_SECURITY_ID),
                under_exchange_segment=INDEX_EXCHANGE_SEGMENT,
            )
            payload = result.get("data", {}) if isinstance(result, dict) else {}
            raw = payload.get("data", []) if isinstance(payload, dict) else []
            expiries: list[str] = []
            for item in raw:
                candidate = None
                if isinstance(item, dict):
                    for key in ("expiry", "expiry_date", "expiryDate"):
                        if item.get(key):
                            candidate = str(item[key])
                            break
                elif item:
                    candidate = str(item)
                if candidate and re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
                    expiries.append(candidate)
            return expiries
        except Exception:  # noqa: BLE001
            return []

    def _fetch_vix(self) -> float | None:
        try:
            today = date.today()
            from_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
            to_date = today.strftime("%Y-%m-%d")
            result = self._client().historical_daily_data(
                security_id=VIX_INDEX_SECURITY_ID,
                exchange_segment=INDEX_EXCHANGE_SEGMENT,
                instrument_type=INDEX_INSTRUMENT_TYPE,
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
            response = self._client().option_chain(
                under_security_id=int(NIFTY_INDEX_SECURITY_ID),
                under_exchange_segment=INDEX_EXCHANGE_SEGMENT,
                expiry=expiry,
            )
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
        security_id_to_symbol: dict[str, str] = {}
        spot = float(body.get("last_price") or 0.0)
        prev_close = float(body.get("prev_close") or body.get("previous_close") or 0.0)

        # Dhan option chain doesn't provide prev_close at top level — derive from daily candles
        if prev_close == 0.0 and self.last_known_prev_close == 0.0:
            try:
                daily = self._fetch_candles("D")
                if daily.get("candles"):
                    # Use second-to-last candle's close as prev_close (last candle is today)
                    candles = daily["candles"]
                    if len(candles) >= 2:
                        prev_close = float(candles[-2]["close"])
                    elif candles:
                        prev_close = float(candles[-1]["close"])
            except Exception:  # noqa: BLE001
                pass

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
            if call["security_id"]:
                security_id_to_symbol[call["security_id"]] = call["symbol"]
            if put["security_id"]:
                security_id_to_symbol[put["security_id"]] = put["symbol"]
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
            "security_id_to_symbol": security_id_to_symbol,
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

    def _build_feed_instruments(self) -> set[tuple[int, str, int]]:
        instruments: set[tuple[int, str, int]] = {(IDX, "13", Quote)}
        for quote in self.quotes.values():
            security_id = quote.get("security_id")
            if security_id:
                instruments.add((NSE_FNO, str(security_id), Full))
        return instruments

    def _build_quote_batch(self, symbols: tuple[str, ...]) -> dict[str, Any]:
        return {
            "active_expiry": self.active_expiry,
            "updated_at": datetime.now(timezone.utc),
            "quotes": [dict(self.quotes[symbol]) for symbol in symbols if symbol in self.quotes],
        }

    def _handle_feed_packet(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return

        if self.snapshot.get("degraded_reason") == "MARKET_FEED_DISCONNECTED":
            self.snapshot["degraded"] = False
            self.snapshot["degraded_reason"] = None
            self.snapshot["updated_at"] = datetime.now(timezone.utc)
            self._snapshot_dirty = True

        security_id = payload.get("security_id")
        if security_id is None:
            return

        security_id_str = str(security_id)
        if security_id_str == "13":
            self._apply_index_tick(payload)

        symbol = self._security_id_to_symbol.get(security_id_str)
        if symbol:
            self._apply_option_tick(symbol, payload)

    def _apply_index_tick(self, payload: dict[str, Any]) -> None:
        ltp = self._safe_float(payload.get("LTP"))
        if ltp is None or ltp <= 0:
            return

        prev_close = self._safe_float(payload.get("close") or payload.get("prev_close"))
        if prev_close and prev_close > 0:
            self.last_known_prev_close = prev_close

        effective_prev = self.last_known_prev_close
        change = round(ltp - effective_prev, 2) if effective_prev else self.last_known_change
        change_pct = round((change / effective_prev) * 100, 2) if effective_prev else self.last_known_change_pct

        if self.snapshot.get("spot") == ltp and self.snapshot.get("change") == change and self.snapshot.get("change_pct") == change_pct:
            return

        self.last_known_spot = ltp
        self.last_known_change = change
        self.last_known_change_pct = change_pct
        self.snapshot["spot"] = ltp
        self.snapshot["change"] = change
        self.snapshot["change_pct"] = change_pct
        self.snapshot["market_status"] = market_status()
        self.snapshot["updated_at"] = datetime.now(timezone.utc)
        self._snapshot_dirty = True

    def _apply_option_tick(self, symbol: str, payload: dict[str, Any]) -> None:
        quote = self.quotes.get(symbol)
        if not quote:
            return

        changed = False
        ltp = self._safe_float(payload.get("LTP"))
        if ltp is not None and ltp > 0 and quote.get("ltp") != ltp:
            quote["ltp"] = ltp
            changed = True

        volume = self._safe_float(payload.get("volume"))
        if volume is not None and quote.get("volume") != volume:
            quote["volume"] = volume
            changed = True

        oi = self._safe_float(payload.get("OI"))
        if oi is not None and quote.get("oi") != oi:
            quote["oi"] = oi
            quote["oi_lakhs"] = round(oi / 100000, 2) if oi else None
            self._pcr_dirty = True
            changed = True

        depth = payload.get("depth")
        if isinstance(depth, list) and depth:
            best_level = depth[0] or {}
            bid = self._safe_float(best_level.get("bid_price") or best_level.get("bid"))
            ask = self._safe_float(best_level.get("ask_price") or best_level.get("ask"))
            bid_qty = self._safe_int(best_level.get("bid_quantity") or best_level.get("bid_qty"))
            ask_qty = self._safe_int(best_level.get("ask_quantity") or best_level.get("ask_qty"))

            if quote.get("bid") != bid:
                quote["bid"] = bid
                changed = True
            if quote.get("ask") != ask:
                quote["ask"] = ask
                changed = True
            if quote.get("bid_qty") != bid_qty:
                quote["bid_qty"] = bid_qty
                changed = True
            if quote.get("ask_qty") != ask_qty:
                quote["ask_qty"] = ask_qty
                changed = True

        if changed:
            self._dirty_quote_symbols.add(symbol)

    def _compute_pcr(self) -> float | None:
        total_call_oi = 0.0
        total_put_oi = 0.0
        for row in self.option_rows:
            total_call_oi += float(row["call"].get("oi") or 0.0)
            total_put_oi += float(row["put"].get("oi") or 0.0)
        return round(total_put_oi / total_call_oi, 2) if total_call_oi else None

    @staticmethod
    def _sorted_instruments(instruments: set[tuple[int, str, int]]) -> list[tuple[int, str, int]]:
        return sorted(instruments, key=lambda item: (item[2], item[0], item[1]))

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            if value is None or value == "":
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_security_id(payload: dict[str, Any]) -> str | None:
        for key in ("security_id", "securityId", "drv_security_id", "drvSecurityId", "instrument_id", "id"):
            if payload.get(key):
                return str(payload[key])
        return None

    async def get_candles(self, timeframe: str, *, before: int | None = None) -> dict[str, Any]:
        if not self._has_dhan():
            return {
                "timeframe": timeframe,
                "candles": [],
                "source": "none",
                "degraded": True,
                "has_more": False,
                "next_before": None,
            }

        try:
            return await asyncio.to_thread(self._fetch_candles, timeframe, before)
        except Exception:  # noqa: BLE001
            return {
                "timeframe": timeframe,
                "candles": [],
                "source": "dhan",
                "degraded": True,
                "has_more": False,
                "next_before": None,
            }

    def _fetch_candles(self, timeframe: str, before: int | None = None) -> dict[str, Any]:
        client = self._client()
        lower_date, upper_date, oldest_date = self._history_window(timeframe, before)
        if timeframe == "D":
            result = client.historical_daily_data(
                security_id=NIFTY_INDEX_SECURITY_ID,
                exchange_segment=INDEX_EXCHANGE_SEGMENT,
                instrument_type=INDEX_INSTRUMENT_TYPE,
                from_date=lower_date.strftime("%Y-%m-%d"),
                to_date=upper_date.strftime("%Y-%m-%d"),
            )
            payload = result.get("data", {}) if isinstance(result, dict) else {}
            candles = self._filter_history_before(self._map_candles(payload), before)
            has_more = lower_date > oldest_date
            return {
                "timeframe": timeframe,
                "candles": candles,
                "source": "dhan",
                "degraded": not candles,
                "has_more": has_more,
                "next_before": self._next_history_cursor(
                    candles,
                    lower_date=lower_date,
                    oldest_date=oldest_date,
                    has_more=has_more,
                ),
            }

        interval = INTRADAY_INTERVALS.get(timeframe, INTRADAY_INTERVALS["15m"])
        result = client.intraday_minute_data(
            security_id=NIFTY_INDEX_SECURITY_ID,
            exchange_segment=INDEX_EXCHANGE_SEGMENT,
            instrument_type=INDEX_INSTRUMENT_TYPE,
            from_date=lower_date.strftime("%Y-%m-%d"),
            to_date=upper_date.strftime("%Y-%m-%d"),
            interval=interval,
        )
        payload = result.get("data", {}) if isinstance(result, dict) else {}
        candles = self._filter_history_before(self._map_candles(payload), before)
        has_more = lower_date > oldest_date
        return {
            "timeframe": timeframe,
            "candles": candles,
            "source": "dhan",
            "degraded": not candles,
            "has_more": has_more,
            "next_before": self._next_history_cursor(
                candles,
                lower_date=lower_date,
                oldest_date=oldest_date,
                has_more=has_more,
            ),
        }

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
