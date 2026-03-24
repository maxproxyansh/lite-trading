from __future__ import annotations

import asyncio
import logging
import math
import market_hours
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from dhanhq import dhanhq as Dhanhq
from dhanhq.marketfeed import DhanFeed, Full, IDX, NSE_FNO, Quote, market_feed_wss, websockets

from config import get_settings
from database import SessionLocal
from market_hours import IST, is_market_open, is_trading_day, market_status, now_ist
from models import DhanInstrumentRegistry
from schemas import DhanConsumerStateUpdateRequest, DhanProviderHealth, MarketSnapshot, OptionChainResponse
from services.dhan_credential_service import DhanApiError, _payload_is_no_data, dhan_credential_service
from services.dhan_incident_service import dhan_incident_service
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
TOKEN_ALERT_REASONS = frozenset(
    {
        "DHAN_AUTH_FAILED",
        "DHAN_PROFILE_FAILED",
        "DHAN_TOKEN_RENEWAL_FAILED",
        "DHAN_TOKEN_REGENERATION_FAILED",
    }
)
TOKEN_ALERT_SUMMARIES = {
    "DHAN_AUTH_FAILED": "auth failed",
    "DHAN_PROFILE_FAILED": "profile check failed",
    "DHAN_TOKEN_RENEWAL_FAILED": "renewal failed",
    "DHAN_TOKEN_REGENERATION_FAILED": "regeneration failed",
}
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
CANDLE_CACHE_TTL = {
    "D": 300, "W": 300, "M": 300,     # daily+ timeframes: 5 min TTL
    "1m": 60, "5m": 60, "15m": 60, "1h": 60,  # intraday: 60s TTL
}
INDEX_SYMBOL_ALIASES = {"NIFTY", "NIFTY 50", "NIFTY50"}
VIX_SYMBOL_ALIASES = {"INDIA VIX", "VIX", "INDIAVIX"}
OPTION_SYMBOL_PATTERN = re.compile(r"^(?P<root>[A-Z0-9]+)_(?P<expiry>\d{4}-\d{2}-\d{2})_(?P<strike>\d+)_(?P<option_type>CE|PE)$")

BroadcastFn = Callable[[str, dict[str, Any]], Awaitable[None]]
ProcessOrdersFn = Callable[[set[str]], Awaitable[None]]


@dataclass(frozen=True)
class CandleInstrument:
    symbol: str
    security_id: str
    exchange_segment: str
    instrument_type: str
    trusted: bool = True


class CandleQueryError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class LiteDhanFeed(DhanFeed):
    async def connect(self):
        if not self.ws or self.ws.closed:
            if self.version == "v1":
                self.ws = await websockets.connect(market_feed_wss, ping_interval=None, ping_timeout=None)
                await self.authorize()
            elif self.version == "v2":
                url = f"{market_feed_wss}?version=2&token={self.access_token}&clientId={self.client_id}&authType=2"
                # The service already watches feed freshness itself. Disabling the
                # library keepalive prevents noisy ping-timeout disconnects from
                # fighting with the app-level reconnect logic.
                self.ws = await websockets.connect(url, ping_interval=None, ping_timeout=None, close_timeout=1)
            else:
                raise ValueError(f"Unsupported version: {self.version}")
            await self.subscribe_instruments()


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
        self._feed_recv_task: asyncio.Task | None = None
        self._feed_token_generation = 0
        self._desired_feed_instruments: set[tuple[int, str, int]] = set()
        self._subscribed_feed_instruments: set[tuple[int, str, int]] = set()
        self._security_id_to_symbol: dict[str, str] = {}
        self._dirty_quote_symbols: set[str] = set()
        self._snapshot_dirty = False
        self._chain_dirty = False
        self._pcr_dirty = False
        self._health_synced_to_db = False
        self._candle_cache: dict[tuple, tuple[float, dict[str, Any]]] = {}  # (sec_id, tf, from, to) -> (ts, data)
        self._live_session_candle_cache: dict[tuple[str, str, str], tuple[float, dict[str, Any] | None]] = {}
        self._chain_cache: dict[str, tuple[float, dict[str, Any]]] = {}  # expiry -> (monotonic_ts, chain_result)
        self._chain_cache_ttl: float = 5.0  # reuse chain results fetched within 5 seconds
        self._inflight_candles: dict[tuple, asyncio.Future] = {}  # dedup concurrent candle requests
        self._option_metadata: dict[str, CandleInstrument] = {}  # symbol -> CandleInstrument (survives chain refreshes)
        self._active_atm_strike: int | None = None

    @staticmethod
    def _normalize_expiry_value(value: str | None) -> str | None:
        candidate = (value or "").strip()
        if not candidate:
            return None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            return candidate
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return None

    @classmethod
    def _normalize_expiries(cls, expiries: list[str]) -> list[str]:
        normalized = {candidate for raw in expiries if (candidate := cls._normalize_expiry_value(raw))}
        return sorted(normalized)

    @staticmethod
    def _registry_observed_at(value: datetime | None = None) -> datetime:
        observed_at = value or datetime.now(timezone.utc)
        return observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=timezone.utc)

    @staticmethod
    def _registry_boundary_timestamp(value: datetime) -> int:
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return int(normalized.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    def _registry_target_from_record(self, record: DhanInstrumentRegistry) -> CandleInstrument:
        return CandleInstrument(
            symbol=record.symbol,
            security_id=record.security_id,
            exchange_segment=record.exchange_segment,
            instrument_type=record.instrument_type,
        )

    def _lookup_registry_by_symbol(self, symbol: str) -> CandleInstrument | None:
        with SessionLocal() as db:
            record = (
                db.query(DhanInstrumentRegistry)
                .filter(DhanInstrumentRegistry.symbol == symbol)
                .one_or_none()
            )
            if record is None:
                return None
            return self._registry_target_from_record(record)

    def _lookup_registry_by_security_id(self, security_id: str) -> CandleInstrument | None:
        with SessionLocal() as db:
            record = (
                db.query(DhanInstrumentRegistry)
                .filter(DhanInstrumentRegistry.security_id == str(security_id))
                .one_or_none()
            )
            if record is None:
                return None
            return self._registry_target_from_record(record)

    def _registry_history_boundary(self, target: CandleInstrument) -> datetime | None:
        if target.instrument_type != OPTION_INSTRUMENT_TYPE:
            return None
        with SessionLocal() as db:
            record = (
                db.query(DhanInstrumentRegistry)
                .filter(DhanInstrumentRegistry.symbol == target.symbol)
                .one_or_none()
            )
            if record is None:
                return None
            return record.first_seen

    def _upsert_option_registry(
        self,
        quotes: dict[str, dict[str, Any]],
        *,
        observed_at: datetime | None = None,
        first_seen_hint: datetime | None = None,
    ) -> None:
        if not quotes:
            return
        observed = self._registry_observed_at(observed_at)
        first_seen_dt = self._registry_observed_at(first_seen_hint) if first_seen_hint else observed
        with SessionLocal() as db:
            for quote in quotes.values():
                symbol = self._normalize_symbol(str(quote.get("symbol") or ""))
                security_id = self._extract_security_id(quote)
                parsed = self._parse_option_symbol(symbol or "")
                if not symbol or not security_id or parsed is None:
                    continue
                expiry, strike, option_type = parsed
                record = (
                    db.query(DhanInstrumentRegistry)
                    .filter(
                        (DhanInstrumentRegistry.symbol == symbol)
                        | (DhanInstrumentRegistry.security_id == str(security_id))
                    )
                    .one_or_none()
                )
                if record is None:
                    record = DhanInstrumentRegistry(
                        symbol=symbol,
                        security_id=str(security_id),
                        root_symbol="NIFTY",
                        exchange_segment=OPTION_EXCHANGE_SEGMENT,
                        instrument_type=OPTION_INSTRUMENT_TYPE,
                        expiry=expiry,
                        strike=strike,
                        option_type=option_type,
                        first_seen=first_seen_dt,
                        last_seen=observed,
                    )
                    db.add(record)
                    continue

                record.symbol = symbol
                record.security_id = str(security_id)
                record.root_symbol = "NIFTY"
                record.exchange_segment = OPTION_EXCHANGE_SEGMENT
                record.instrument_type = OPTION_INSTRUMENT_TYPE
                record.expiry = expiry
                record.strike = strike
                record.option_type = option_type
                existing_first_seen = self._registry_observed_at(record.first_seen)
                existing_last_seen = self._registry_observed_at(record.last_seen)
                record.first_seen = min(existing_first_seen, first_seen_dt)
                record.last_seen = max(existing_last_seen, observed)
            db.commit()

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
            return market_hours.now_ist()
        return datetime.fromtimestamp(before, timezone.utc).astimezone(IST)

    @staticmethod
    def _market_today() -> date:
        return market_hours.now_ist().date()

    @staticmethod
    def _atm_strike_for_spot(spot: float | None) -> int | None:
        if spot is None or spot <= 0:
            return None
        return int(math.floor((spot + 25) / 50) * 50)

    def _refresh_active_atm_strike(self, spot: float | None) -> bool:
        next_atm = self._atm_strike_for_spot(spot)
        if self._active_atm_strike == next_atm:
            return False
        self._active_atm_strike = next_atm
        return True

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
        seed_spot = False
        seed_vix = False
        try:
            await self.refresh()
        except Exception as exc:
            logger.error("Initial market data refresh failed (background loops will retry): %s", exc)
        if not self.last_known_spot or not self.last_known_prev_close:
            seed_spot = True
            await self._seed_spot_from_history()
        if not self.snapshot.get("vix"):
            seed_vix = True
            await self._seed_vix_from_history()
        if seed_spot or seed_vix:
            await self._broadcast_snapshot()
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        self._feed_task = asyncio.create_task(self._feed_loop())
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def _seed_spot_from_history(self) -> None:
        """Seed snapshot spot from the last daily candle (works on weekends/holidays)."""
        try:
            payload = await asyncio.to_thread(
                lambda: dhan_credential_service.call(
                    "bootstrap_spot_history",
                    lambda client: client.historical_daily_data(
                        security_id=NIFTY_INDEX_SECURITY_ID,
                        exchange_segment=INDEX_EXCHANGE_SEGMENT,
                        instrument_type="INDEX",
                        from_date=(market_hours.now_ist().date() - timedelta(days=7)).strftime("%Y-%m-%d"),
                        to_date=market_hours.now_ist().date().strftime("%Y-%m-%d"),
                    ),
                ),
            )
            candles = self._map_candles(payload if isinstance(payload, dict) else {}, normalize_daily=True)
            if candles:
                last = candles[-1]
                last_close = float(last["close"])
                had_live_spot = self.last_known_spot > 0
                effective_spot = self.last_known_spot if had_live_spot else last_close
                if not had_live_spot:
                    self.last_known_spot = last_close
                    self.snapshot["spot"] = last_close
                self.snapshot["updated_at"] = datetime.now(timezone.utc)
                if len(candles) >= 2:
                    last_candle_date = datetime.fromtimestamp(int(last["time"]), timezone.utc).astimezone(IST).date()
                    current_ist_date = self._market_today()
                    use_latest_close_as_prev = had_live_spot and is_market_open() and last_candle_date < current_ist_date
                    prev_close = float(last["close"] if use_latest_close_as_prev else candles[-2]["close"])
                    self.last_known_prev_close = prev_close
                    change = round(effective_spot - prev_close, 2)
                    change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0
                    self.last_known_change = change
                    self.last_known_change_pct = change_pct
                    self.snapshot["change"] = change
                    self.snapshot["change_pct"] = change_pct
                logger.info("Seeded spot/change from history: spot=%.2f prev_close=%.2f", effective_spot, self.last_known_prev_close)
        except Exception as exc:
            logger.warning("Failed to seed spot from history: %s", exc)

    async def _seed_vix_from_history(self) -> None:
        """Seed VIX from the latest daily candle when the feed has not populated it yet."""
        try:
            payload = await asyncio.to_thread(
                lambda: dhan_credential_service.call(
                    "bootstrap_vix_history",
                    lambda client: client.historical_daily_data(
                        security_id=VIX_INDEX_SECURITY_ID,
                        exchange_segment=INDEX_EXCHANGE_SEGMENT,
                        instrument_type="INDEX",
                        from_date=(market_hours.now_ist().date() - timedelta(days=7)).strftime("%Y-%m-%d"),
                        to_date=market_hours.now_ist().date().strftime("%Y-%m-%d"),
                    ),
                ),
            )
            candles = self._map_candles(payload if isinstance(payload, dict) else {}, normalize_daily=True)
            if not candles:
                return
            last_close = float(candles[-1]["close"])
            if last_close <= 0:
                return
            self.snapshot["vix"] = last_close
            self.last_vix_refresh = datetime.now(timezone.utc)
            self.snapshot["updated_at"] = datetime.now(timezone.utc)
            logger.info("Seeded VIX from history: vix=%.2f", last_close)
        except Exception as exc:
            logger.warning("Failed to seed VIX from history: %s", exc)

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
        self._feed_recv_task = None
        self._desired_feed_instruments = set()
        self._subscribed_feed_instruments = set()
        self._security_id_to_symbol = {}
        self._dirty_quote_symbols = set()
        self._snapshot_dirty = False
        self._chain_dirty = False
        self._pcr_dirty = False
        self._health_synced_to_db = False
        self._candle_cache.clear()
        self._live_session_candle_cache.clear()
        self._chain_cache.clear()
        self._option_metadata.clear()
        self._active_atm_strike = None
        dhan_incident_service.reset_runtime_state_for_tests()

    def get_provider_health(self) -> DhanProviderHealth:
        credentials = dhan_credential_service.snapshot()
        incident = dhan_incident_service.snapshot()
        incident_reason = incident.root_cause or self._health.incident_reason
        incident_message = incident.message or self._health.incident_message
        incident_open = incident.incident_open or self._health.incident_open

        if not credentials.configured and not incident_reason:
            incident_open = True
            incident_reason = "DHAN_NOT_CONFIGURED"
            incident_message = "Dhan credentials are missing"

        return DhanProviderHealth(
            configured=credentials.configured,
            authority_mode="lite",
            p0_status="critical" if incident_open else "ok",
            incident_open=incident_open,
            incident_class=incident.incident_class,
            incident_fingerprint=incident.fingerprint,
            incident_reason=incident_reason,
            incident_message=incident_message,
            incident_since=incident.opened_at if incident.incident_open else None,
            affected_consumers=incident.affected_consumers,
            token_source=credentials.token_source,
            token_expires_at=credentials.expires_at,
            last_token_refresh_at=credentials.last_refreshed_at,
            last_profile_check_at=credentials.last_profile_checked_at,
            last_lease_issued_at=credentials.last_lease_issued_at,
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
            consumer_states=incident.consumer_states,
        )

    async def record_consumer_state(self, payload: DhanConsumerStateUpdateRequest) -> None:
        await asyncio.to_thread(
            dhan_incident_service.mark_consumer_state,
            consumer=payload.consumer,
            instance_id=payload.instance_id,
            state=payload.state,
            reason=payload.reason,
            message=payload.message,
            observed_at=payload.observed_at,
            generation=payload.generation,
            alert_sender=self._send_incident_alert_sync,
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

    def _build_slack_alert(
        self,
        *,
        state: str,
        reason: str,
    ) -> tuple[str, list[str]] | None:
        normalized_reason = (reason or "").strip()
        if normalized_reason.startswith("PROVIDER_UNHEALTHY:"):
            _, normalized_reason = normalized_reason.split(":", 1)
        if normalized_reason not in TOKEN_ALERT_REASONS:
            return None

        if state == "RECOVERY":
            token_source = (self.get_provider_health().token_source or "").lower()
            if token_source == "totp":
                return "[RECOVERY] Dhan token regenerated", []
            return "[RECOVERY] Dhan token recovered", []

        summary = TOKEN_ALERT_SUMMARIES.get(normalized_reason, normalized_reason.lower().replace("_", " "))
        return "[P0] Dhan token failed", [summary]

    async def _send_incident_alert(self, *, state: str, reason: str, message: str) -> bool:
        if not settings.dhan_p0_slack_webhook_url:
            return False
        alert = self._build_slack_alert(state=state, reason=reason)
        if not alert:
            return True
        title, lines = alert
        return await send_p0_slack_alert(title=title, lines=lines)

    def _send_incident_alert_sync(
        self,
        *,
        state: str,
        incident_class: str,
        reason: str,
        message: str,
    ) -> bool:
        try:
            return asyncio.run(
                self._send_incident_alert(
                    state=state,
                    reason=f"{incident_class}:{reason}",
                    message=message,
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to deliver persisted Dhan incident alert")
            return False

    async def _open_incident(self, reason: str, message: str) -> None:
        self._health_synced_to_db = False
        now = datetime.now(timezone.utc)
        self._health.incident_open = True
        if not self._health.incident_since:
            self._health.incident_since = now
        self._health.incident_reason = reason
        self._health.incident_message = message
        self._health.last_error_at = now
        self._health.last_error_reason = reason
        self._health.last_error_message = message
        if reason in {"MARKET_FEED_DISCONNECTED", "REALTIME_FEED_STALE"}:
            self._invalidate_stale_live_quotes(now=now)
        self.snapshot["degraded"] = True
        self.snapshot["degraded_reason"] = reason
        self.snapshot["updated_at"] = now
        self._snapshot_dirty = True
        await asyncio.to_thread(
            dhan_incident_service.set_provider_health,
            unhealthy=True,
            reason=reason,
            message=message,
            alert_sender=self._send_incident_alert_sync,
        )

    def _invalidate_stale_live_quotes(self, *, now: datetime) -> None:
        live_quote_fields = ("ltp", "bid", "ask", "bid_qty", "ask_qty", "oi", "oi_lakhs", "volume", "day_high", "day_low")
        for quote in self.quotes.values():
            live_updated_at = self._parse_timestamp(quote.get("_live_updated_at"))
            if live_updated_at is None or self._is_live_quote_fresh(live_updated_at, now=now):
                continue
            changed = False
            for field in live_quote_fields:
                if quote.get(field) is not None:
                    quote[field] = None
                    changed = True
            if changed:
                self._dirty_quote_symbols.add(quote["symbol"])

    async def _close_incident(self, message: str = "Dhan market data recovered") -> None:
        if not self._health.incident_open:
            if self._health_synced_to_db:
                return
            await asyncio.to_thread(
                dhan_incident_service.set_provider_health,
                unhealthy=False,
                reason=None,
                message=None,
                alert_sender=self._send_incident_alert_sync,
            )
            self._health_synced_to_db = True
            return
        now = datetime.now(timezone.utc)

        self._health.incident_open = False
        self._health.incident_since = None
        self._health.incident_reason = None
        self._health.incident_message = None
        self._health.last_recovery_alert_at = now
        self.snapshot["degraded"] = False
        self.snapshot["degraded_reason"] = None
        self.snapshot["updated_at"] = now
        self._snapshot_dirty = True
        await asyncio.to_thread(
            dhan_incident_service.set_provider_health,
            unhealthy=False,
            reason=None,
            message=None,
            alert_sender=self._send_incident_alert_sync,
        )
        self._health_synced_to_db = True

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
            chain_dirty = self._chain_dirty
            if not dirty_symbols and not snapshot_dirty and not chain_dirty:
                continue

            if snapshot_dirty:
                await self._broadcast_snapshot()
                self._snapshot_dirty = False

            if chain_dirty:
                await self._broadcast_chain()
                self._chain_dirty = False

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
                if market_status() != "OPEN":
                    # Feed is not expected when market is closed — clear any
                    # stale MARKET_FEED_DISCONNECTED incident and wait.
                    if self._health.incident_open and self._health.incident_reason in (
                        "MARKET_FEED_DISCONNECTED",
                        "REALTIME_FEED_STALE",
                    ):
                        await self._close_incident()
                    await self._reset_feed()
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
                    payload = await self._recv_feed_payload(timeout=5.0)
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
            except websockets.ConnectionClosed:
                logger.info("Dhan realtime feed closed; reconnecting")
                await self._open_incident("MARKET_FEED_DISCONNECTED", "Dhan realtime feed disconnected unexpectedly")
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
        self._feed = LiteDhanFeed(
            credentials.client_id,
            credentials.access_token,
            instruments,
            version="v2",
        )
        await self._feed.connect()
        self._subscribed_feed_instruments = set(instruments)
        self._feed_token_generation = credentials.generation
        self._feed_recv_task = None

    async def _recv_feed_payload(self, *, timeout: float) -> dict[str, Any] | None:
        if not self._feed:
            return None
        if self._feed_recv_task is None:
            self._feed_recv_task = asyncio.create_task(self._feed.get_instrument_data())
        try:
            payload = await asyncio.wait_for(asyncio.shield(self._feed_recv_task), timeout=timeout)
        except asyncio.TimeoutError:
            raise
        else:
            self._feed_recv_task = None
            return payload

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
        if self._feed_recv_task:
            self._feed_recv_task.cancel()
            try:
                await self._feed_recv_task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                pass
            self._feed_recv_task = None
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
                market_today = self._market_today()
                if expiry_date < market_today and self.expiries:
                    future = [expiry for expiry in self.expiries if expiry >= market_today.isoformat()]
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
            chain = await asyncio.to_thread(self._fetch_option_chain_cached, self.active_expiry)
        except DhanApiError as exc:
            # On weekends/holidays, Dhan returns "Invalid Expiry Date" — serve cached data silently
            if "invalid expiry" in exc.message.lower() and self.option_rows:
                logger.info("Option chain unavailable (likely market closed) — serving cached data")
                await self._close_incident()
                await self._broadcast_snapshot()
                return
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

        # VIX is now sourced from the WebSocket feed (_apply_vix_tick).

        await self._evaluate_provider_health()
        await self._broadcast_snapshot()
        await self._broadcast_chain()
        self._chain_dirty = False

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
        chain = await asyncio.to_thread(self._fetch_option_chain_cached, requested)
        if not chain:
            return False
        self._apply_chain_payload(chain, expiry=requested, now=datetime.now(timezone.utc))
        self._chain_dirty = False
        return True

    def get_snapshot(self) -> MarketSnapshot:
        return MarketSnapshot(**self.snapshot)

    def get_option_chain(self, expiry: str | None = None) -> OptionChainResponse:
        active_atm = self._active_atm_strike
        if active_atm is None:
            active_atm = self._atm_strike_for_spot(self.last_known_spot or self._safe_float(self.snapshot.get("spot")))
        rows = [
            {
                **row,
                "is_atm": row["strike"] == active_atm if active_atm is not None else bool(row.get("is_atm")),
                "call": self._quote_for_chain_response(row["call"]),
                "put": self._quote_for_chain_response(row["put"]),
            }
            for row in self.option_rows
        ]
        return OptionChainResponse(snapshot=self.get_snapshot(), rows=rows)

    @staticmethod
    def _quote_for_chain_response(quote: dict[str, Any]) -> dict[str, Any]:
        payload = dict(quote)
        payload["ltp"] = MarketDataService._safe_float(payload.get("ltp"))
        return payload

    def _apply_chain_payload(self, chain: dict[str, Any], *, expiry: str, now: datetime) -> None:
        self.active_expiry = expiry
        incoming_quotes = chain["quotes"]
        incoming_sid_map = chain["security_id_to_symbol"]
        self._upsert_option_registry(incoming_quotes, observed_at=now)

        rest_only_fields = ("iv", "delta", "gamma", "theta", "vega")
        live_quote_fields = ("ltp", "bid", "ask", "bid_qty", "ask_qty", "oi", "oi_lakhs", "volume", "day_high", "day_low")

        for symbol, incoming in incoming_quotes.items():
            existing = self.quotes.get(symbol)
            if existing:
                merged = dict(incoming)
                live_updated_at = self._parse_timestamp(existing.get("_live_updated_at"))
                live_is_fresh = self._is_live_quote_fresh(live_updated_at, now=now)
                if live_is_fresh:
                    for field in live_quote_fields:
                        if existing.get(field) is not None:
                            merged[field] = existing[field]
                for field in rest_only_fields:
                    val = incoming.get(field)
                    if val is not None:
                        merged[field] = val
                if not merged.get("security_id") and existing.get("security_id"):
                    merged["security_id"] = existing["security_id"]
                if live_updated_at is not None:
                    merged["_live_updated_at"] = live_updated_at
                self.quotes[symbol] = merged
            else:
                self.quotes[symbol] = incoming

        # Remove strikes that are no longer in the chain (expiry changed, etc.)
        stale_symbols = set(self.quotes) - set(incoming_quotes)
        for symbol in stale_symbols:
            del self.quotes[symbol]

        # Rebuild rows from current quotes (includes merged data)
        self.option_rows = chain["rows"]
        # Update rows to reference current (merged) quotes
        for row in self.option_rows:
            call_sym = row["call"].get("symbol") if isinstance(row["call"], dict) else None
            put_sym = row["put"].get("symbol") if isinstance(row["put"], dict) else None
            if call_sym and call_sym in self.quotes:
                row["call"] = self.quotes[call_sym]
            if put_sym and put_sym in self.quotes:
                row["put"] = self.quotes[put_sym]

        self._security_id_to_symbol = {**self._security_id_to_symbol, **incoming_sid_map}
        # Clean stale security_id mappings
        valid_sids = {str(q.get("security_id")) for q in self.quotes.values() if q.get("security_id")}
        self._security_id_to_symbol = {k: v for k, v in self._security_id_to_symbol.items() if k in valid_sids}

        self._health.last_option_chain_success_at = now
        self._health.last_market_data_at = now

        # Seed spot from REST if WebSocket hasn't provided it yet (e.g. weekends, startup)
        rest_spot = chain.get("spot")
        if rest_spot and rest_spot > 0 and not self.last_known_spot:
            self.last_known_spot = rest_spot
            self.snapshot["spot"] = rest_spot
        self._refresh_active_atm_strike(self.last_known_spot or rest_spot)

        pcr = round(chain["total_put_oi"] / chain["total_call_oi"], 2) if chain.get("total_call_oi") else None
        self.snapshot["pcr"] = pcr
        self.snapshot["pcr_scope"] = PCR_SCOPE
        self.snapshot["call_oi_total"] = round(chain.get("total_call_oi", 0), 2)
        self.snapshot["put_oi_total"] = round(chain.get("total_put_oi", 0), 2)
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

    @staticmethod
    def _vix_history_target() -> CandleInstrument:
        return CandleInstrument(
            symbol="INDIA VIX",
            security_id=VIX_INDEX_SECURITY_ID,
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
        return self.quotes.get(symbol)

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
        if normalized_security_id == VIX_INDEX_SECURITY_ID:
            return self._vix_history_target()

        if normalized_security_id:
            quote = self._lookup_quote_by_security_id(normalized_security_id)
            if quote:
                return self._history_target_from_quote(quote)
            registry_target = self._lookup_registry_by_security_id(normalized_security_id)
            if registry_target:
                return registry_target
            if normalized_symbol and self._parse_option_symbol(normalized_symbol) is not None:
                return CandleInstrument(
                    symbol=normalized_symbol,
                    security_id=normalized_security_id,
                    exchange_segment=OPTION_EXCHANGE_SEGMENT,
                    instrument_type=OPTION_INSTRUMENT_TYPE,
                    trusted=False,
                )
            if not normalized_symbol:
                raise CandleQueryError(status_code=404, detail="SECURITY_ID_NOT_AVAILABLE")

        if not normalized_symbol or normalized_symbol in INDEX_SYMBOL_ALIASES:
            return self._index_history_target()
        if normalized_symbol in VIX_SYMBOL_ALIASES:
            return self._vix_history_target()

        # Check cached option metadata first — avoids chain fetch entirely
        cached_target = self._option_metadata.get(normalized_symbol)
        if cached_target:
            return cached_target

        quote = self._lookup_quote_by_symbol(normalized_symbol)
        if quote:
            return self._history_target_from_quote(quote)

        registry_target = self._lookup_registry_by_symbol(normalized_symbol)
        if registry_target:
            return registry_target

        if self._parse_option_symbol(normalized_symbol) is None:
            raise CandleQueryError(
                status_code=400,
                detail="Unsupported symbol format. Expected NIFTY 50, INDIA VIX/VIX, or NIFTY_YYYY-MM-DD_STRIKE_CE|PE",
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
        now = market_hours.now_ist()
        if timeframe in INTRADAY_INTERVALS:
            interval = INTRADAY_INTERVALS[timeframe]
            if interval == 60:
                bucket_dt = now.replace(minute=0, second=0, microsecond=0)
            else:
                bucket_dt = now.replace(
                    minute=(now.minute // interval) * interval,
                    second=0,
                    microsecond=0,
                )
            return int(bucket_dt.timestamp())
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
        day_high: float | None = None,
        day_low: float | None = None,
    ) -> list[dict[str, Any]]:
        if live_price is None or live_price <= 0:
            return candles

        bucket_time = MarketDataService._current_bucket_time(timeframe)
        if candles and bucket_time < int(candles[-1]["time"]):
            return candles
        if timeframe in INTRADAY_INTERVALS and candles:
            bucket_dt = datetime.fromtimestamp(bucket_time, timezone.utc).astimezone(IST)
            last_dt = datetime.fromtimestamp(int(candles[-1]["time"]), timezone.utc).astimezone(IST)
            if last_dt.date() < bucket_dt.date() - timedelta(days=1):
                return candles
        # day_high/day_low only apply to daily-based timeframes (D/W/M).
        # For intraday candles they represent the full session range and must
        # NOT be folded into a single interval bar.
        is_daily = timeframe in DAILY_HISTORY_TIMEFRAMES

        if candles and int(candles[-1]["time"]) == bucket_time:
            last = candles[-1]
            high = max(float(last["high"]), live_price)
            low = min(float(last["low"]), live_price)
            if is_daily and day_high and day_high > 0:
                high = max(high, day_high)
            if is_daily and day_low and day_low > 0:
                low = min(low, day_low)
            next_candle = {
                **last,
                "high": high,
                "low": low,
                "close": live_price,
            }
            return [*candles[:-1], next_candle]

        # Don't create a phantom candle on weekends / holidays
        if not is_trading_day():
            return candles

        open_price = float(candles[-1]["close"]) if candles else live_price
        high = max(open_price, live_price)
        low = min(open_price, live_price)
        if is_daily and day_high and day_high > 0:
            high = max(high, day_high)
        if is_daily and day_low and day_low > 0:
            low = min(low, day_low)
        return [
            *candles,
            {
                "time": bucket_time,
                "open": open_price,
                "high": high,
                "low": low,
                "close": live_price,
                "volume": 0.0,
            },
        ]

    def _build_live_session_candle(
        self,
        target: CandleInstrument,
        *,
        timeframe: str,
        live_price: float | None,
        day_high: float | None,
        day_low: float | None,
    ) -> dict[str, Any] | None:
        if timeframe not in DAILY_HISTORY_TIMEFRAMES or not is_trading_day():
            return None
        if not any(value and value > 0 for value in (live_price, day_high, day_low)):
            return None

        market_today = self._market_today()
        cache_key = (target.security_id, timeframe, market_today.isoformat())
        cache_ttl = CANDLE_CACHE_TTL.get("1m", 60)
        cached = self._live_session_candle_cache.get(cache_key)
        now = time.monotonic()
        base_candle: dict[str, Any] | None = None
        if cached and now - cached[0] < cache_ttl:
            base_candle = cached[1]

        if base_candle is None:
            payload = dhan_credential_service.call(
                "intraday_minute_data",
                lambda dhan_client: dhan_client.intraday_minute_data(
                    security_id=target.security_id,
                    exchange_segment=target.exchange_segment,
                    instrument_type=target.instrument_type,
                    from_date=market_today.strftime("%Y-%m-%d"),
                    to_date=market_today.strftime("%Y-%m-%d"),
                    interval=1,
                ),
            )
            session_candles = self._map_candles(payload if isinstance(payload, dict) else {})
            if not session_candles:
                self._live_session_candle_cache[cache_key] = (now, None)
                return None
            base_candle = {
                "open": float(session_candles[0]["open"]),
                "high": max(float(candle["high"]) for candle in session_candles),
                "low": min(float(candle["low"]) for candle in session_candles),
                "close": float(session_candles[-1]["close"]),
                "volume": float(sum(float(candle.get("volume") or 0.0) for candle in session_candles)),
            }
            self._live_session_candle_cache[cache_key] = (now, base_candle)

        high = float(base_candle["high"])
        low = float(base_candle["low"])
        close = float(base_candle["close"])
        if live_price and live_price > 0:
            close = live_price
            high = max(high, live_price)
            low = min(low, live_price)
        if day_high and day_high > 0:
            high = max(high, day_high)
        if day_low and day_low > 0:
            low = min(low, day_low)

        candle = {
            "time": self._current_bucket_time(timeframe),
            "open": float(base_candle["open"]),
            "high": high,
            "low": low,
            "close": close,
            "volume": float(base_candle["volume"]),
        }
        return candle

    def _live_ohlc_for_target(
        self, target: CandleInstrument,
    ) -> tuple[float | None, float | None, float | None]:
        """Return (live_price, day_high, day_low) for the given target."""
        if target.security_id == NIFTY_INDEX_SECURITY_ID:
            live_spot = self._safe_float(self.snapshot.get("spot"))
            price = live_spot if live_spot and live_spot > 0 else self.last_known_spot or None
            return price, self._safe_float(self.snapshot.get("day_high")), self._safe_float(self.snapshot.get("day_low"))
        if target.security_id == VIX_INDEX_SECURITY_ID:
            live_vix = self._safe_float(self.snapshot.get("vix"))
            return (live_vix if live_vix and live_vix > 0 else None), None, None

        quote = self._lookup_quote_by_security_id(target.security_id)
        if not quote:
            quote = self._lookup_quote_by_symbol(target.symbol)
        if not quote:
            return None, None, None
        live_price = self._safe_float(quote.get("ltp"))
        price = live_price if live_price and live_price > 0 else None
        return price, self._safe_float(quote.get("day_high")), self._safe_float(quote.get("day_low"))

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
            normalized = self._normalize_expiry_value(candidate)
            if normalized:
                expiries.append(normalized)
        return self._normalize_expiries(expiries)

    def _fetch_option_chain_cached(self, expiry: str) -> dict[str, Any] | None:
        """Return a recent chain result if available, otherwise fetch fresh."""
        now = time.monotonic()
        cached = self._chain_cache.get(expiry)
        if cached and now - cached[0] < self._chain_cache_ttl:
            return cached[1]
        result = self._fetch_option_chain(expiry)
        if result is not None:
            self._chain_cache[expiry] = (now, result)
            # Populate option metadata for chart symbol lookups
            for sym, quote in result.get("quotes", {}).items():
                sid = self._extract_security_id(quote)
                if sid:
                    self._option_metadata[sym] = CandleInstrument(
                        symbol=sym, security_id=str(sid),
                        exchange_segment=OPTION_EXCHANGE_SEGMENT,
                        instrument_type=OPTION_INSTRUMENT_TYPE,
                    )
            self._upsert_option_registry(result.get("quotes", {}))
        return result

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

        # Use live WebSocket spot for ATM calculation, fallback to REST
        spot = self.last_known_spot or float(body.get("last_price") or 0.0)
        atm = self._atm_strike_for_spot(spot)

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

        return {
            "quotes": quotes,
            "rows": rows,
            "security_id_to_symbol": security_id_to_symbol,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "spot": spot if spot else None,
        }

    def _map_option_quote(self, payload: dict[str, Any], expiry: str, strike: int, option_type: str) -> dict[str, Any]:
        best_bid = next(
            (v for k in ("best_bid_price", "top_bid_price", "bid", "bestBidPrice", "topBidPrice")
             if (v := payload.get(k)) is not None),
            None,
        )
        best_ask = next(
            (v for k in ("best_ask_price", "top_ask_price", "ask", "bestAskPrice", "topAskPrice")
             if (v := payload.get(k)) is not None),
            None,
        )
        bid_qty = next(
            (v for k in ("best_bid_qty", "top_bid_quantity", "bestBidQty", "topBidQuantity")
             if (v := payload.get(k)) is not None),
            None,
        )
        ask_qty = next(
            (v for k in ("best_ask_qty", "top_ask_quantity", "bestAskQty", "topAskQuantity")
             if (v := payload.get(k)) is not None),
            None,
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
            "ltp": self._safe_float(payload.get("last_price") or payload.get("ltp")),
            "bid": float(best_bid) if best_bid is not None else None,
            "ask": float(best_ask) if best_ask is not None else None,
            "bid_qty": self._safe_int(bid_qty),
            "ask_qty": self._safe_int(ask_qty),
            "iv": self._safe_float(payload.get("implied_volatility") or payload.get("iv")),
            "oi": raw_oi,
            "oi_lakhs": round(raw_oi / 100000, 2) if raw_oi is not None else None,
            "volume": self._safe_float(payload.get("volume") or payload.get("traded_volume")),
            "delta": self._safe_float(greeks.get("delta")),
            "gamma": self._safe_float(greeks.get("gamma")),
            "theta": self._safe_float(greeks.get("theta")),
            "vega": self._safe_float(greeks.get("vega")),
        }

    def _build_feed_instruments(self) -> set[tuple[int, str, int]]:
        instruments: set[tuple[int, str, int]] = {
            (IDX, NIFTY_INDEX_SECURITY_ID, Quote),
            (IDX, VIX_INDEX_SECURITY_ID, Quote),  # VIX live via feed
        }
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
        if security_id_str == NIFTY_INDEX_SECURITY_ID:
            self._apply_index_tick(payload)
        elif security_id_str == VIX_INDEX_SECURITY_ID:
            self._apply_vix_tick(payload)

        symbol = self._security_id_to_symbol.get(security_id_str)
        if symbol:
            self._apply_option_tick(symbol, payload)

    def _apply_index_tick(self, payload: dict[str, Any]) -> None:
        ltp = self._safe_float(payload.get("LTP"))
        if ltp is None or ltp <= 0:
            return
        atm_changed = self._refresh_active_atm_strike(ltp)

        prev_close = self._safe_float(payload.get("close") or payload.get("prev_close"))
        if prev_close and prev_close > 0:
            self.last_known_prev_close = prev_close

        # Day high/low from Dhan Full feed
        day_high = self._safe_float(payload.get("high"))
        day_low = self._safe_float(payload.get("low"))

        effective_prev = self.last_known_prev_close
        change = round(ltp - effective_prev, 2) if effective_prev else self.last_known_change
        change_pct = round((change / effective_prev) * 100, 2) if effective_prev else self.last_known_change_pct
        next_day_high = self.snapshot.get("day_high")
        next_day_low = self.snapshot.get("day_low")
        if day_high and day_high > 0:
            next_day_high = day_high
        if day_low and day_low > 0:
            next_day_low = day_low
        next_market_status = market_status()

        if (
            self.snapshot.get("spot") == ltp
            and self.snapshot.get("change") == change
            and self.snapshot.get("change_pct") == change_pct
            and self.snapshot.get("day_high") == next_day_high
            and self.snapshot.get("day_low") == next_day_low
            and self.snapshot.get("market_status") == next_market_status
            and not atm_changed
        ):
            return

        self.last_known_spot = ltp
        self.last_known_change = change
        self.last_known_change_pct = change_pct
        self.snapshot["spot"] = ltp
        self.snapshot["change"] = change
        self.snapshot["change_pct"] = change_pct
        if next_day_high is not None:
            self.snapshot["day_high"] = next_day_high
        if next_day_low is not None:
            self.snapshot["day_low"] = next_day_low
        self.snapshot["market_status"] = next_market_status
        self.snapshot["updated_at"] = datetime.now(timezone.utc)
        self._snapshot_dirty = True
        if atm_changed:
            self._chain_dirty = True

    def _apply_vix_tick(self, payload: dict[str, Any]) -> None:
        ltp = self._safe_float(payload.get("LTP"))
        if ltp is None or ltp <= 0:
            return
        if self.snapshot.get("vix") != ltp:
            self.snapshot["vix"] = ltp
            self.last_vix_refresh = datetime.now(timezone.utc)
            self._snapshot_dirty = True

    def _apply_option_tick(self, symbol: str, payload: dict[str, Any]) -> None:
        quote = self.quotes.get(symbol)
        if not quote:
            return

        now = datetime.now(timezone.utc)
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
            quote["oi_lakhs"] = round(oi / 100000, 2) if oi is not None else None
            self._pcr_dirty = True
            changed = True

        # Day high/low from Dhan Full feed (same fields as index tick)
        day_high = self._safe_float(payload.get("high"))
        if day_high is not None and day_high > 0 and quote.get("day_high") != day_high:
            quote["day_high"] = day_high
            changed = True
        day_low = self._safe_float(payload.get("low"))
        if day_low is not None and day_low > 0 and quote.get("day_low") != day_low:
            quote["day_low"] = day_low
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
            quote["_live_updated_at"] = now
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
    def _parse_timestamp(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @staticmethod
    def _is_live_quote_fresh(updated_at: datetime | None, *, now: datetime) -> bool:
        if updated_at is None:
            return False
        freshness_window = timedelta(seconds=max(settings.dhan_realtime_stale_seconds, settings.market_feed_reconnect_seconds * 2))
        return now - updated_at <= freshness_window

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

        # Deduplicate concurrent identical requests — only one hits Dhan
        dedup_key = (timeframe, before, symbol, security_id)
        existing = self._inflight_candles.get(dedup_key)
        if existing and not existing.done():
            return await asyncio.shield(existing)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        future.add_done_callback(
            lambda fut: None if fut.cancelled() else fut.exception()  # noqa: B023
        )
        self._inflight_candles[dedup_key] = future

        try:
            result = await asyncio.to_thread(
                self._fetch_candles,
                timeframe,
                before,
                symbol=symbol,
                security_id=security_id,
            )
            if not future.done():
                future.set_result(result)
            return result
        except CandleQueryError as exc:
            if not future.done():
                future.set_exception(exc)
            raise
        except DhanApiError as exc:
            status_code = 503
            if exc.reason == "DHAN_INVALID_REQUEST":
                status_code = 400
            elif exc.reason == "DHAN_RATE_LIMITED":
                status_code = 429
            err = CandleQueryError(status_code=status_code, detail=exc.reason)
            if not future.done():
                future.set_exception(err)
            raise err from exc
        except Exception:  # noqa: BLE001
            fallback = {
                "timeframe": timeframe,
                "candles": [],
                "source": "dhan",
                "degraded": True,
                "has_more": False,
                "next_before": None,
            }
            if not future.done():
                future.set_result(fallback)
            return fallback
        finally:
            self._inflight_candles.pop(dedup_key, None)

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
        first_seen_boundary = self._registry_history_boundary(target)
        no_data = False
        if (
            timeframe in DAILY_HISTORY_TIMEFRAMES
            and before is not None
            and first_seen_boundary is not None
            and before <= self._registry_boundary_timestamp(first_seen_boundary)
        ):
            return {
                "timeframe": timeframe,
                "candles": [],
                "source": "registry",
                "degraded": False,
                "has_more": False,
                "next_before": None,
            }

        # --- candle cache lookup / fetch ---
        # For the current window (not scrolling back), key on (security_id, timeframe)
        # so that daily date boundary shifts don't invalidate the cache.
        # For historical pages (before != None), include dates since those are fixed ranges.
        if before is None:
            cache_key = (target.security_id, timeframe, "_current_")
        else:
            cache_key = (target.security_id, timeframe, lower_date.isoformat(), upper_date.isoformat())
        ttl = CANDLE_CACHE_TTL.get(timeframe, 60)
        now = time.monotonic()
        cached = self._candle_cache.get(cache_key)
        if cached is not None and now - cached[0] < ttl:
            payload = cached[1]
            no_data = _payload_is_no_data(payload)
        elif timeframe in DAILY_HISTORY_TIMEFRAMES:
            try:
                payload = dhan_credential_service.call(
                    "chart_historical_daily_data",
                    lambda dhan_client: dhan_client.historical_daily_data(
                        security_id=target.security_id,
                        exchange_segment=target.exchange_segment,
                        instrument_type=target.instrument_type,
                        from_date=lower_date.strftime("%Y-%m-%d"),
                        to_date=upper_date.strftime("%Y-%m-%d"),
                    ),
                )
            except DhanApiError as exc:
                if exc.reason == "DHAN_NO_DATA":
                    no_data = True
                    payload = {"errorCode": "DH-907", "errorMessage": "No data present"}
                else:
                    raise
            payload = payload if isinstance(payload, dict) else {}
            self._candle_cache[cache_key] = (now, payload)
        else:
            interval = INTRADAY_INTERVALS.get(timeframe, INTRADAY_INTERVALS["15m"])
            try:
                payload = dhan_credential_service.call(
                    "chart_intraday_minute_data",
                    lambda dhan_client: dhan_client.intraday_minute_data(
                        security_id=target.security_id,
                        exchange_segment=target.exchange_segment,
                        instrument_type=target.instrument_type,
                        from_date=lower_date.strftime("%Y-%m-%d"),
                        to_date=upper_date.strftime("%Y-%m-%d"),
                        interval=interval,
                    ),
                )
            except DhanApiError as exc:
                if exc.reason == "DHAN_NO_DATA":
                    no_data = True
                    payload = {"errorCode": "DH-907", "errorMessage": "No data present"}
                else:
                    raise
            payload = payload if isinstance(payload, dict) else {}
            self._candle_cache[cache_key] = (now, payload)

        # Evict stale cache entries (> 2x max TTL)
        if len(self._candle_cache) > 50:
            stale = [k for k, (ts, _) in self._candle_cache.items() if now - ts > 600]
            for k in stale:
                del self._candle_cache[k]

        # --- process candles ---
        if timeframe in DAILY_HISTORY_TIMEFRAMES:
            candles = self._aggregate_candles(self._map_candles(payload, normalize_daily=True), timeframe)
            if before is None:
                live_price, day_high, day_low = self._live_ohlc_for_target(target)
                current_bucket_time = self._current_bucket_time(timeframe)
                has_current_bucket = bool(candles and int(candles[-1]["time"]) == current_bucket_time)
                if has_current_bucket:
                    candles = self._overlay_live_price(
                        candles,
                        timeframe=timeframe,
                        live_price=live_price,
                        day_high=day_high,
                        day_low=day_low,
                    )
                else:
                    try:
                        live_session_candle = self._build_live_session_candle(
                            target,
                            timeframe=timeframe,
                            live_price=live_price,
                            day_high=day_high,
                            day_low=day_low,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.info(
                            "Failed to build live %s candle from intraday session for %s: %s",
                            timeframe,
                            target.symbol,
                            exc,
                        )
                        live_session_candle = None
                    if live_session_candle:
                        candles = [*candles, live_session_candle]
        else:
            candles = self._map_candles(payload)
            if before is None and market_status() == "OPEN":
                live_price, day_high, day_low = self._live_ohlc_for_target(target)
                candles = self._overlay_live_price(
                    candles,
                    timeframe=timeframe,
                    live_price=live_price,
                    day_high=day_high,
                    day_low=day_low,
                )

        candles = self._filter_history_before(candles, before)
        if candles and target.instrument_type == OPTION_INSTRUMENT_TYPE and target.trusted and timeframe == "D":
            first_seen_at = datetime.fromtimestamp(int(candles[0]["time"]), timezone.utc)
            last_seen_at = datetime.fromtimestamp(int(candles[-1]["time"]), timezone.utc)
            self._upsert_option_registry(
                {
                    target.symbol: {
                        "symbol": target.symbol,
                        "security_id": target.security_id,
                    }
                },
                observed_at=last_seen_at,
                first_seen_hint=first_seen_at,
            )
            normalized_first_seen_boundary = self._registry_observed_at(first_seen_boundary) if first_seen_boundary else None
            first_seen_boundary = first_seen_at if normalized_first_seen_boundary is None else min(normalized_first_seen_boundary, first_seen_at)
        normalized_boundary = self._registry_observed_at(first_seen_boundary) if first_seen_boundary else None
        boundary_date = normalized_boundary.astimezone(IST).date() if normalized_boundary else oldest_date
        has_more = lower_date > max(oldest_date, boundary_date)
        return {
            "timeframe": timeframe,
            "candles": candles,
            "source": "dhan",
            "degraded": False if no_data or (before is not None and not candles) else not candles,
            "has_more": has_more,
            "next_before": self._next_history_cursor(
                candles,
                lower_date=lower_date,
                oldest_date=max(oldest_date, boundary_date),
                has_more=has_more,
            ),
        }

    def _map_candles(self, payload: dict[str, Any] | Any, *, normalize_daily: bool = False) -> list[dict[str, Any]]:
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
            if normalize_daily:
                # Normalize to midnight IST so timestamps match _current_bucket_time.
                # Dhan may return midnight UTC; converting to the IST date and
                # rebuilding ensures the overlay comparison works correctly.
                ist_date = dt.astimezone(IST).date()
                dt = datetime.combine(ist_date, datetime.min.time(), tzinfo=IST)
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
