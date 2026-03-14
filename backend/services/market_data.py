from __future__ import annotations

import asyncio
import logging
import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from dhanhq import dhanhq as Dhanhq
from dhanhq.marketfeed import DhanFeed, Full, IDX, NSE_FNO, Quote

from config import get_settings
from market_hours import IST, market_status
from schemas import DhanProviderHealth, MarketSnapshot, OptionChainResponse
from services.dhan_credential_service import DhanApiError, dhan_credential_service
from services.ops_alert_service import send_p0_slack_alert


settings = get_settings()
logger = logging.getLogger("lite.market-data")

NIFTY_INDEX_SECURITY_ID = "13"
VIX_INDEX_SECURITY_ID = "21"
INDEX_EXCHANGE_SEGMENT = "IDX_I"
INDEX_INSTRUMENT_TYPE = "INDEX"
OPTION_EXCHANGE_SEGMENT = "NSE_FNO"
OPTION_INSTRUMENT_TYPE = "OPTIDX"
PCR_SCOPE = "all_loaded_strikes_for_active_expiry"
OLDEST_DAILY_HISTORY = date(1990, 1, 1)
MAX_INTRADAY_HISTORY_DAYS = 365 * 5
INITIAL_HISTORY_WINDOWS = {
    "1m": 30,
    "5m": 90,
    "15m": 90,
    "1h": 90,
    "D": 365,
    "W": 365 * 3,
    "M": 365 * 10,
}
INTRADAY_INTERVALS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}
DAILY_HISTORY_TIMEFRAMES = {"D", "W", "M"}
AGGREGATED_DAILY_TIMEFRAMES = {"W", "M"}
INDEX_SYMBOL_ALIASES = {"NIFTY", "NIFTY 50", "NIFTY50"}
OPTION_SYMBOL_PATTERN = re.compile(r"^(?P<root>[A-Z0-9]+)_(?P<expiry>\d{4}-\d{2}-\d{2})_(?P<strike>\d+)_(?P<option_type>CE|PE)$")

BroadcastFn = Callable[[str, dict[str, Any]], Awaitable[None]]
ProcessOrdersFn = Callable[[set[str]], Awaitable[None]]


@dataclass(frozen=True)
class CandleInstrument:
    symbol: str
    security_id: str
    exchange_segment: str
    instrument_type: str


class CandleQueryError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(slots=True)
class ProviderHealthState:
    incident_open: bool = False
    incident_reason: str | None = None
    incident_message: str | None = None
    incident_since: datetime | None = None
    last_error_at: datetime | None = None
    last_error_reason: str | None = None
    last_error_message: str | None = None
    last_option_chain_success_at: datetime | None = None
    last_feed_message_at: datetime | None = None
    last_market_data_at: datetime | None = None
    last_incident_alert_at: datetime | None = None
    last_recovery_alert_at: datetime | None = None


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
            "pcr_scope": PCR_SCOPE,
            "call_oi_total": 0.0,
            "put_oi_total": 0.0,
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
        self._health = ProviderHealthState()
        self._snapshot_task: asyncio.Task | None = None
        self._feed_task: asyncio.Task | None = None
        self._flush_task: asyncio.Task | None = None
        self._feed: DhanFeed | None = None
        self._feed_token_generation = 0
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
        return dhan_credential_service.configured()

    def _client(self) -> Dhanhq:
        return dhan_credential_service.create_client()

    @staticmethod
    def _history_anchor(before: int | None) -> datetime:
        if before is None:
            return datetime.now(IST)
        return datetime.fromtimestamp(before, timezone.utc).astimezone(IST)

    def _history_window(self, timeframe: str, before: int | None) -> tuple[date, date, date]:
        anchor = self._history_anchor(before)
        upper_date = anchor.date()
        oldest_date = OLDEST_DAILY_HISTORY if timeframe in DAILY_HISTORY_TIMEFRAMES else upper_date - timedelta(days=MAX_INTRADAY_HISTORY_DAYS)
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
        dhan_credential_service.initialize()
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

    def reset_runtime_state_for_tests(self) -> None:
        self._health = ProviderHealthState()
        self._feed_token_generation = 0
        self._desired_feed_instruments = set()
        self._subscribed_feed_instruments = set()
        self._security_id_to_symbol = {}
        self._dirty_quote_symbols = set()
        self._snapshot_dirty = False
        self._pcr_dirty = False

    def get_provider_health(self) -> DhanProviderHealth:
        credentials = dhan_credential_service.snapshot()
        incident_reason = self._health.incident_reason
        incident_message = self._health.incident_message
        incident_open = self._health.incident_open

        if not credentials.configured and not incident_reason:
            incident_open = True
            incident_reason = "DHAN_NOT_CONFIGURED"
            incident_message = "Dhan credentials are missing"

        return DhanProviderHealth(
            configured=credentials.configured,
            p0_status="critical" if incident_open else "ok",
            incident_open=incident_open,
            incident_reason=incident_reason,
            incident_message=incident_message,
            incident_since=self._health.incident_since,
            token_source=credentials.token_source,
            token_expires_at=credentials.expires_at,
            last_token_refresh_at=credentials.last_refreshed_at,
            last_profile_check_at=credentials.last_profile_checked_at,
            last_rest_success_at=credentials.last_rest_success_at,
            last_option_chain_success_at=self._health.last_option_chain_success_at,
            last_feed_message_at=self._health.last_feed_message_at,
            last_market_data_at=self._health.last_market_data_at,
            last_error_at=self._health.last_error_at,
            last_error_reason=self._health.last_error_reason,
            last_error_message=self._health.last_error_message,
            data_plan_status=credentials.data_plan_status,
            data_valid_until=credentials.data_valid_until,
            realtime_stale_after_seconds=max(settings.dhan_realtime_stale_seconds, settings.market_feed_reconnect_seconds * 2),
            chain_stale_after_seconds=max(settings.dhan_rest_stale_seconds, settings.option_chain_refresh_seconds * 2),
            renewal_lead_seconds=settings.dhan_token_renewal_lead_seconds,
            feed_connected=bool(self._feed and self._feed.ws and not self._feed.ws.closed),
            market_open=market_status() == "OPEN",
            slack_configured=bool(settings.dhan_p0_slack_webhook_url),
            totp_regeneration_enabled=credentials.totp_regeneration_enabled,
        )

    async def _ensure_runtime_ready(self, *, force_profile: bool = False) -> None:
        rotated = await asyncio.to_thread(dhan_credential_service.ensure_token_fresh, force_profile)
        credentials = dhan_credential_service.snapshot()
        if rotated or credentials.generation != self._feed_token_generation:
            await self._reset_feed()
        self._feed_token_generation = credentials.generation

    @staticmethod
    def _seconds_since(value: datetime | None, *, now: datetime) -> int | None:
        if value is None:
            return None
        return max(int((now - value).total_seconds()), 0)

    async def _send_incident_alert(self, *, state: str, reason: str, message: str) -> None:
        if not settings.dhan_p0_slack_webhook_url:
            return
        health = self.get_provider_health()
        lines = [
            f"environment: {settings.app_env}",
            f"reason: {reason}",
            f"message: {message}",
            f"token_expires_at: {health.token_expires_at.isoformat() if health.token_expires_at else 'unknown'}",
            f"last_token_refresh_at: {health.last_token_refresh_at.isoformat() if health.last_token_refresh_at else 'never'}",
            f"last_profile_check_at: {health.last_profile_check_at.isoformat() if health.last_profile_check_at else 'never'}",
            f"last_option_chain_success_at: {health.last_option_chain_success_at.isoformat() if health.last_option_chain_success_at else 'never'}",
            f"last_feed_message_at: {health.last_feed_message_at.isoformat() if health.last_feed_message_at else 'never'}",
            "health_path: /api/v1/market/provider-health",
        ]
        title = f"[{state}] Dhan market data"
        await send_p0_slack_alert(title=title, lines=lines)

    async def _open_incident(self, reason: str, message: str) -> None:
        now = datetime.now(timezone.utc)
        cooldown = timedelta(seconds=max(settings.dhan_incident_alert_cooldown_seconds, 60))
        changed = (not self._health.incident_open) or self._health.incident_reason != reason or self._health.incident_message != message
        should_alert = changed or not self._health.last_incident_alert_at or now - self._health.last_incident_alert_at >= cooldown

        self._health.incident_open = True
        if changed or not self._health.incident_since:
            self._health.incident_since = now
        self._health.incident_reason = reason
        self._health.incident_message = message
        self._health.last_error_at = now
        self._health.last_error_reason = reason
        self._health.last_error_message = message
        self.snapshot["degraded"] = True
        self.snapshot["degraded_reason"] = reason
        self.snapshot["updated_at"] = now
        self._snapshot_dirty = True

        if should_alert:
            self._health.last_incident_alert_at = now
            await self._send_incident_alert(state="P0", reason=reason, message=message)

    async def _close_incident(self, message: str = "Dhan market data recovered") -> None:
        if not self._health.incident_open:
            return
        reason = self._health.incident_reason or "RECOVERED"
        self._health.incident_open = False
        self._health.incident_since = None
        self._health.incident_reason = None
        self._health.incident_message = None
        self._health.last_recovery_alert_at = datetime.now(timezone.utc)
        self.snapshot["degraded"] = False
        self.snapshot["degraded_reason"] = None
        self.snapshot["updated_at"] = datetime.now(timezone.utc)
        self._snapshot_dirty = True
        await self._send_incident_alert(state="RECOVERY", reason=reason, message=message)

    async def _evaluate_provider_health(self) -> None:
        now = datetime.now(timezone.utc)
        credentials = dhan_credential_service.snapshot()
        if not credentials.configured:
            await self._open_incident("DHAN_NOT_CONFIGURED", "Dhan credentials are missing")
            return

        if credentials.data_plan_status and credentials.data_plan_status.lower() != "active":
            await self._open_incident(
                "DHAN_DATA_PLAN_INACTIVE",
                f"Dhan data plan is {credentials.data_plan_status} and market data is unavailable",
            )
            return

        chain_stale_after = timedelta(seconds=max(settings.dhan_rest_stale_seconds, settings.option_chain_refresh_seconds * 2))
        if self._health.last_option_chain_success_at and now - self._health.last_option_chain_success_at > chain_stale_after:
            age = self._seconds_since(self._health.last_option_chain_success_at, now=now)
            await self._open_incident("OPTION_CHAIN_STALE", f"Last successful option-chain refresh is {age}s old")
            return

        if market_status() == "OPEN" and self._desired_feed_instruments:
            realtime_stale_after = timedelta(seconds=max(settings.dhan_realtime_stale_seconds, settings.market_feed_reconnect_seconds * 2))
            feed_age = self._seconds_since(self._health.last_feed_message_at, now=now)
            if self._health.last_feed_message_at is None:
                if self._health.last_option_chain_success_at and now - self._health.last_option_chain_success_at > realtime_stale_after:
                    await self._open_incident(
                        "REALTIME_FEED_STALE",
                        "No Dhan realtime feed packets arrived after the latest option-chain refresh",
                    )
                    await self._reset_feed()
                    return
            elif feed_age is not None and timedelta(seconds=feed_age) > realtime_stale_after:
                await self._open_incident("REALTIME_FEED_STALE", f"Last Dhan realtime feed packet is {feed_age}s old")
                await self._reset_feed()
                return

        await self._close_incident()

    async def _snapshot_loop(self) -> None:
        interval = max(settings.option_chain_refresh_seconds, 1)
        while True:
            try:
                await self.refresh()
            except DhanApiError as exc:
                await self._open_incident(exc.reason, exc.message)
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected Dhan market refresh failure")
                await self._open_incident("MARKET_REFRESH_FAILED", "Unexpected exception while refreshing Dhan market data")
            await asyncio.sleep(interval)

    async def _flush_loop(self) -> None:
        interval = max(settings.market_feed_flush_ms, 50) / 1000
        while True:
            await asyncio.sleep(interval)
            if self._pcr_dirty:
                pcr, call_oi_total, put_oi_total = self._pcr_metrics()
                self.snapshot["pcr"] = pcr
                self.snapshot["pcr_scope"] = PCR_SCOPE
                self.snapshot["call_oi_total"] = call_oi_total
                self.snapshot["put_oi_total"] = put_oi_total
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
                await self._ensure_runtime_ready(force_profile=not self._feed)
                if not self._feed or not self._feed.ws or self._feed.ws.closed:
                    await self._connect_feed()
                await self._sync_feed_subscriptions()
                try:
                    # dhanhq exposes get_instrument_data() as an async recv wrapper; wait_for prevents a stuck socket.
                    payload = await asyncio.wait_for(self._feed.get_instrument_data(), timeout=5.0)
                except asyncio.TimeoutError:
                    await self._evaluate_provider_health()
                    continue
                if payload:
                    self._handle_feed_packet(payload)
                    await self._evaluate_provider_health()
            except asyncio.CancelledError:
                raise
            except DhanApiError as exc:
                await self._open_incident(exc.reason, exc.message)
                await self._reset_feed()
                await asyncio.sleep(reconnect_delay)
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected Dhan feed disconnect")
                await self._open_incident("MARKET_FEED_DISCONNECTED", "Dhan realtime feed disconnected unexpectedly")
                await self._reset_feed()
                await asyncio.sleep(reconnect_delay)

    async def _connect_feed(self) -> None:
        credentials = dhan_credential_service.snapshot()
        if not credentials.client_id or not credentials.access_token:
            raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan credentials are missing for the realtime feed")
        instruments = self._sorted_instruments(self._desired_feed_instruments)
        self._feed = DhanFeed(
            credentials.client_id,
            credentials.access_token,
            instruments,
            version="v2",
        )
        await self._feed.connect()
        self._subscribed_feed_instruments = set(instruments)
        self._feed_token_generation = credentials.generation

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
            await self._open_incident("DHAN_NOT_CONFIGURED", "Dhan credentials are missing")
            await self._broadcast_snapshot()
            return

        await self._ensure_runtime_ready()
        now = datetime.now(timezone.utc)
        if not self.last_expiry_refresh or now - self.last_expiry_refresh > timedelta(minutes=10):
            try:
                self.expiries = await asyncio.to_thread(self._fetch_expiries)
            except DhanApiError as exc:
                await self._open_incident(exc.reason, exc.message)
                await self._broadcast_snapshot()
                return
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
            await self._open_incident("NO_EXPIRIES", "Dhan did not return any tradable expiries")
            await self._broadcast_snapshot()
            return

        try:
            chain = await asyncio.to_thread(self._fetch_option_chain, self.active_expiry)
        except DhanApiError as exc:
            await self._open_incident(exc.reason, exc.message)
            await self._broadcast_snapshot()
            return
        if not chain:
            if self.option_rows:
                await self._open_incident("OPTION_CHAIN_STALE", "Dhan option-chain refresh failed and the cached chain is now stale")
                await self._broadcast_snapshot()
                return
            await self._open_incident("OPTION_CHAIN_UNAVAILABLE", "Dhan option-chain data is unavailable")
            await self._broadcast_snapshot()
            return

        self._apply_chain_payload(chain, expiry=self.active_expiry, now=now)

        if not self.last_vix_refresh or now - self.last_vix_refresh > timedelta(minutes=5):
            try:
                vix = await asyncio.to_thread(self._fetch_vix)
            except DhanApiError as exc:
                logger.warning("Dhan VIX refresh failed: %s", exc.message)
            else:
                if vix is not None:
                    self.snapshot["vix"] = vix
            self.last_vix_refresh = now

        await self._evaluate_provider_health()
        await self._broadcast_snapshot()
        await self._broadcast_chain()

    async def _broadcast_snapshot(self) -> None:
        if self._broadcast:
            await self._broadcast("market.snapshot", self.get_snapshot().model_dump(mode="json"))

    async def _broadcast_chain(self) -> None:
        if self._broadcast:
            response = self.get_option_chain()
            await self._broadcast("option.chain", response.model_dump(mode="json"))

    def set_active_expiry(self, expiry: str) -> None:
        self.active_expiry = expiry

    async def activate_expiry(self, expiry: str) -> bool:
        requested = expiry.strip()
        if not requested:
            return False
        if self.expiries and requested not in self.expiries:
            return False
        chain = await asyncio.to_thread(self._fetch_option_chain, requested)
        if not chain:
            return False
        self._apply_chain_payload(chain, expiry=requested, now=datetime.now(timezone.utc))
        return True

    def get_snapshot(self) -> MarketSnapshot:
        return MarketSnapshot(**self.snapshot)

    def get_option_chain(self, expiry: str | None = None) -> OptionChainResponse:
        return OptionChainResponse(snapshot=self.get_snapshot(), rows=self.option_rows)

    def _apply_chain_payload(self, chain: dict[str, Any], *, expiry: str, now: datetime) -> None:
        self.active_expiry = expiry
        self.option_rows = chain["rows"]
        self.quotes = chain["quotes"]
        self._security_id_to_symbol = chain["security_id_to_symbol"]
        self._health.last_option_chain_success_at = now
        self._health.last_market_data_at = now
        self.snapshot.update(chain["snapshot"])
        self.snapshot["expiries"] = self.expiries
        self.snapshot["active_expiry"] = expiry
        self.snapshot["market_status"] = market_status()
        self.snapshot["degraded"] = False
        self.snapshot["degraded_reason"] = None
        self.snapshot["updated_at"] = now
        self._desired_feed_instruments = self._build_feed_instruments()
        self._dirty_quote_symbols.clear()
        self._pcr_dirty = False

    def get_quote(self, symbol: str) -> dict[str, Any] | None:
        return self.quotes.get(symbol)

    def resolve_symbol(self, *, expiry: str, strike: int, option_type: str) -> str:
        return f"NIFTY_{expiry}_{strike}_{option_type.upper()}"

    def get_depth(self, symbol: str) -> dict[str, Any] | None:
        return self.quotes.get(symbol)

    @staticmethod
    def _normalize_symbol(symbol: str | None) -> str | None:
        candidate = (symbol or "").strip().upper()
        return candidate or None

    @staticmethod
    def _index_history_target() -> CandleInstrument:
        return CandleInstrument(
            symbol="NIFTY 50",
            security_id=NIFTY_INDEX_SECURITY_ID,
            exchange_segment=INDEX_EXCHANGE_SEGMENT,
            instrument_type=INDEX_INSTRUMENT_TYPE,
        )

    def _lookup_quote_by_security_id(self, security_id: str) -> dict[str, Any] | None:
        security_id_str = str(security_id)
        symbol = self._security_id_to_symbol.get(security_id_str)
        if symbol:
            return self.quotes.get(symbol)
        for quote in self.quotes.values():
            if str(quote.get("security_id") or "") == security_id_str:
                return quote
        return None

    @staticmethod
    def _parse_option_symbol(symbol: str) -> tuple[str, int, str] | None:
        match = OPTION_SYMBOL_PATTERN.fullmatch(symbol)
        if not match or match.group("root") != "NIFTY":
            return None
        return match.group("expiry"), int(match.group("strike")), match.group("option_type")

    def _history_target_from_quote(self, quote: dict[str, Any]) -> CandleInstrument:
        security_id = self._extract_security_id(quote)
        symbol = str(quote.get("symbol") or "")
        if not security_id or not symbol:
            raise CandleQueryError(status_code=503, detail="QUOTE_METADATA_INCOMPLETE")
        return CandleInstrument(
            symbol=symbol,
            security_id=str(security_id),
            exchange_segment=OPTION_EXCHANGE_SEGMENT,
            instrument_type=OPTION_INSTRUMENT_TYPE,
        )

    def _lookup_quote_by_symbol(self, symbol: str) -> dict[str, Any] | None:
        quote = self.quotes.get(symbol)
        if quote:
            return quote

        parsed = self._parse_option_symbol(symbol)
        if not parsed:
            return None

        expiry, _strike, _option_type = parsed
        # Fall back to a fresh option-chain lookup so chart loads are not limited to the currently visible expiry.
        chain = self._fetch_option_chain(expiry)
        if not chain:
            raise CandleQueryError(status_code=503, detail="OPTION_METADATA_UNAVAILABLE")
        return chain.get("quotes", {}).get(symbol)

    def _resolve_candle_target(
        self,
        *,
        symbol: str | None = None,
        security_id: str | None = None,
    ) -> CandleInstrument:
        normalized_symbol = self._normalize_symbol(symbol)
        normalized_security_id = str(security_id).strip() if security_id else None

        if normalized_security_id == NIFTY_INDEX_SECURITY_ID:
            return self._index_history_target()

        if normalized_security_id:
            quote = self._lookup_quote_by_security_id(normalized_security_id)
            if quote:
                return self._history_target_from_quote(quote)
            if not normalized_symbol:
                raise CandleQueryError(status_code=404, detail="SECURITY_ID_NOT_AVAILABLE")

        if not normalized_symbol or normalized_symbol in INDEX_SYMBOL_ALIASES:
            return self._index_history_target()

        quote = self._lookup_quote_by_symbol(normalized_symbol)
        if quote:
            return self._history_target_from_quote(quote)

        if self._parse_option_symbol(normalized_symbol) is None:
            raise CandleQueryError(
                status_code=400,
                detail="Unsupported symbol format. Expected NIFTY 50 or NIFTY_YYYY-MM-DD_STRIKE_CE|PE",
            )
        raise CandleQueryError(status_code=404, detail="SYMBOL_NOT_AVAILABLE")

    @staticmethod
    def _aggregate_candles(candles: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:
        if timeframe not in AGGREGATED_DAILY_TIMEFRAMES:
            return candles

        buckets: dict[int, dict[str, Any]] = {}
        for candle in sorted(candles, key=lambda item: item["time"]):
            dt = datetime.fromtimestamp(candle["time"], timezone.utc).astimezone(IST)
            if timeframe == "W":
                bucket_date = dt.date() - timedelta(days=dt.weekday())
            else:
                bucket_date = dt.date().replace(day=1)
            bucket_time = int(datetime.combine(bucket_date, datetime.min.time(), tzinfo=IST).timestamp())

            bucket = buckets.get(bucket_time)
            if bucket is None:
                buckets[bucket_time] = {
                    "time": bucket_time,
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"]),
                    "volume": float(candle.get("volume") or 0.0),
                }
                continue

            bucket["high"] = max(float(bucket["high"]), float(candle["high"]))
            bucket["low"] = min(float(bucket["low"]), float(candle["low"]))
            bucket["close"] = float(candle["close"])
            bucket["volume"] = float(bucket["volume"]) + float(candle.get("volume") or 0.0)

        return [buckets[key] for key in sorted(buckets)]

    @staticmethod
    def _current_bucket_time(timeframe: str) -> int:
        now = datetime.now(timezone.utc).astimezone(IST)
        if timeframe == "W":
            bucket_date = now.date() - timedelta(days=now.weekday())
        elif timeframe == "M":
            bucket_date = now.date().replace(day=1)
        else:
            bucket_date = now.date()
        return int(datetime.combine(bucket_date, datetime.min.time(), tzinfo=IST).timestamp())

    @staticmethod
    def _overlay_live_price(
        candles: list[dict[str, Any]],
        *,
        timeframe: str,
        live_price: float | None,
    ) -> list[dict[str, Any]]:
        if live_price is None or live_price <= 0:
            return candles

        bucket_time = MarketDataService._current_bucket_time(timeframe)
        if candles and int(candles[-1]["time"]) == bucket_time:
            last = candles[-1]
            next_candle = {
                **last,
                "high": max(float(last["high"]), live_price),
                "low": min(float(last["low"]), live_price),
                "close": live_price,
            }
            return [*candles[:-1], next_candle]

        open_price = float(candles[-1]["close"]) if candles else live_price
        return [
            *candles,
            {
                "time": bucket_time,
                "open": open_price,
                "high": max(open_price, live_price),
                "low": min(open_price, live_price),
                "close": live_price,
                "volume": 0.0,
            },
        ]

    def _live_price_for_target(self, target: CandleInstrument) -> float | None:
        if target.security_id == NIFTY_INDEX_SECURITY_ID:
            live_spot = self._safe_float(self.snapshot.get("spot"))
            return live_spot if live_spot and live_spot > 0 else self.last_known_spot or None

        quote = self._lookup_quote_by_security_id(target.security_id)
        if not quote:
            quote = self._lookup_quote_by_symbol(target.symbol)
        if not quote:
            return None
        live_price = self._safe_float(quote.get("ltp"))
        return live_price if live_price and live_price > 0 else None

    def _fetch_expiries(self) -> list[str]:
        result = dhan_credential_service.call(
            "expiry_list",
            lambda client: client.expiry_list(
                under_security_id=int(NIFTY_INDEX_SECURITY_ID),
                under_exchange_segment=INDEX_EXCHANGE_SEGMENT,
            ),
        )
        payload = result if isinstance(result, dict) else {}
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

    def _fetch_vix(self) -> float | None:
        today = date.today()
        from_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
        result = dhan_credential_service.call(
            "historical_daily_data.vix",
            lambda client: client.historical_daily_data(
                security_id=VIX_INDEX_SECURITY_ID,
                exchange_segment=INDEX_EXCHANGE_SEGMENT,
                instrument_type=INDEX_INSTRUMENT_TYPE,
                from_date=from_date,
                to_date=to_date,
            ),
        )
        payload = result if isinstance(result, dict) else {}
        closes = payload.get("close", []) if isinstance(payload, dict) else []
        return float(closes[-1]) if closes else None

    def _fetch_option_chain(self, expiry: str) -> dict[str, Any] | None:
        response = dhan_credential_service.call(
            "option_chain",
            lambda client: client.option_chain(
                under_security_id=int(NIFTY_INDEX_SECURITY_ID),
                under_exchange_segment=INDEX_EXCHANGE_SEGMENT,
                expiry=expiry,
            ),
        )

        body = response if isinstance(response, dict) else {}
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
                "pcr_scope": PCR_SCOPE,
                "call_oi_total": round(total_call_oi, 2),
                "put_oi_total": round(total_put_oi, 2),
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

        security_id = payload.get("security_id")
        if security_id is None:
            return
        now = datetime.now(timezone.utc)
        self._health.last_feed_message_at = now
        self._health.last_market_data_at = now

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

    def _pcr_metrics(self) -> tuple[float | None, float, float]:
        total_call_oi = 0.0
        total_put_oi = 0.0
        for row in self.option_rows:
            total_call_oi += float(row["call"].get("oi") or 0.0)
            total_put_oi += float(row["put"].get("oi") or 0.0)
        pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else None
        return pcr, round(total_call_oi, 2), round(total_put_oi, 2)

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

    async def get_candles(
        self,
        timeframe: str,
        *,
        before: int | None = None,
        symbol: str | None = None,
        security_id: str | None = None,
    ) -> dict[str, Any]:
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
            return await asyncio.to_thread(
                self._fetch_candles,
                timeframe,
                before,
                symbol=symbol,
                security_id=security_id,
            )
        except CandleQueryError:
            raise
        except DhanApiError as exc:
            raise CandleQueryError(status_code=503, detail=exc.reason) from exc
        except Exception:  # noqa: BLE001
            return {
                "timeframe": timeframe,
                "candles": [],
                "source": "dhan",
                "degraded": True,
                "has_more": False,
                "next_before": None,
            }

    def _fetch_candles(
        self,
        timeframe: str,
        before: int | None = None,
        *,
        symbol: str | None = None,
        security_id: str | None = None,
    ) -> dict[str, Any]:
        target = self._resolve_candle_target(symbol=symbol, security_id=security_id)
        lower_date, upper_date, oldest_date = self._history_window(timeframe, before)
        if timeframe in DAILY_HISTORY_TIMEFRAMES:
            payload = dhan_credential_service.call(
                "historical_daily_data",
                lambda dhan_client: dhan_client.historical_daily_data(
                    security_id=target.security_id,
                    exchange_segment=target.exchange_segment,
                    instrument_type=target.instrument_type,
                    from_date=lower_date.strftime("%Y-%m-%d"),
                    to_date=upper_date.strftime("%Y-%m-%d"),
                ),
            )
            payload = payload if isinstance(payload, dict) else {}
            candles = self._aggregate_candles(self._map_candles(payload), timeframe)
            if before is None:
                candles = self._overlay_live_price(
                    candles,
                    timeframe=timeframe,
                    live_price=self._live_price_for_target(target),
                )
            candles = self._filter_history_before(candles, before)
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
        payload = dhan_credential_service.call(
            "intraday_minute_data",
            lambda dhan_client: dhan_client.intraday_minute_data(
                security_id=target.security_id,
                exchange_segment=target.exchange_segment,
                instrument_type=target.instrument_type,
                from_date=lower_date.strftime("%Y-%m-%d"),
                to_date=upper_date.strftime("%Y-%m-%d"),
                interval=interval,
            ),
        )
        payload = payload if isinstance(payload, dict) else {}
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

    def _map_candles(self, payload: dict[str, Any] | Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
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
