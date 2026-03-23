from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import struct
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, TypeVar
from urllib.parse import urlsplit

import httpx
from dhanhq import dhanhq as Dhanhq
from config import get_settings
from database import SessionLocal
from market_hours import IST
from models import ServiceCredential

settings = get_settings()
logger = logging.getLogger("lite.dhan.credentials")
T = TypeVar("T")
DHAN_API_BASE = "https://api.dhan.co/v2"
DHAN_AUTH_BASE = "https://auth.dhan.co/app"
AUTH_ERROR_MARKERS = ("authentication failed", "token invalid", "invalid token", "invalid jwt", "unauthorized", "401")
RATE_LIMIT_MARKERS = ("too many request", "too many requests", "429", "805")
STATIC_IP_MARKERS = ("static ip", "whitelisted ip", "ip mismatch")
ACCESS_DENIED_MARKERS = ("not subscribed", "does not have access", "access denied", "subscription")
TOTP_INVALID_MARKERS = ("invalid totp", "totp invalid", "otp invalid", "invalid otp")
TOTP_REGEN_RATE_LIMIT_MARKERS = ("once every 2 minutes", "once in 2 minutes", "wait for 2 minutes")
INVALID_REQUEST_MARKERS = (
    "invalid request",
    "invalid expiry",
    "invalid expiry date",
    "invalid date format",
    "invalid securityid",
    "invalid security id",
    "incorrect parameter",
    "missing required",
    "bad values for parameters",
)
NO_DATA_MARKERS = ("no data", "no data present", "unable to fetch data", "empty data", "no records")

_AUTH_ERROR_CODES = {"DH-901", "DH-906", "807", "808", "809", "810"}
_ACCESS_DENIED_CODES = {"DH-902", "806"}
_ACCOUNT_ERROR_CODES = {"DH-903"}
_RATE_LIMIT_CODES = {"DH-904", "805", "429"}
_INVALID_REQUEST_CODES = {"DH-905", "804", "811", "812", "813", "814"}
_NO_DATA_CODES = {"DH-907"}
_UPSTREAM_ERROR_CODES = {"DH-908", "DH-909", "DH-910", "800"}
_AUTH_HTTP_CODES = {"401", "403"}

_CRITICAL_BUDGET_OPERATIONS = {"profile", "generate_access_token", "renew_token"}
_HIGH_PRIORITY_BUDGET_OPERATIONS = {
    "option_chain",
    "expiry_list",
    "bootstrap_spot_history",
    "bootstrap_vix_history",
}


def _normalize_error_code(error_code: str | int | None) -> str:
    if error_code is None:
        return ""
    return str(error_code).strip().upper()


def _extract_error_details(payload: Any) -> tuple[str, str]:
    error_code = ""
    error_message = ""
    if isinstance(payload, dict):
        direct_code = payload.get("errorCode") or payload.get("error_code") or payload.get("code")
        direct_message = payload.get("errorMessage") or payload.get("error_message") or payload.get("message")
        error_code = _normalize_error_code(direct_code)
        error_message = str(direct_message or "").strip()

        remarks = payload.get("remarks")
        if isinstance(remarks, dict):
            error_code = error_code or _normalize_error_code(remarks.get("error_code") or remarks.get("code"))
            error_message = error_message or str(remarks.get("error_message") or remarks.get("message") or "").strip()
        elif isinstance(remarks, str):
            error_message = error_message or remarks.strip()

        data = payload.get("data")
        if isinstance(data, dict):
            error_code = error_code or _normalize_error_code(data.get("errorCode") or data.get("error_code"))
            error_message = error_message or str(data.get("errorMessage") or data.get("error_message") or data.get("message") or "").strip()

    return error_code, error_message


def _payload_is_no_data(payload: Any) -> bool:
    error_code, error_message = _extract_error_details(payload)
    reason, _ = _classify_dhan_error(error_code, error_message)
    return reason == "DHAN_NO_DATA"


def _classify_dhan_error(error_code: str | int | None, error_message: str | None, *, status: int = 0) -> tuple[str, bool]:
    code = _normalize_error_code(error_code or (str(status) if status else ""))
    msg = (error_message or "").strip()
    msg_lower = msg.lower()
    is_auth = code in _AUTH_ERROR_CODES or code in _AUTH_HTTP_CODES or status in {401, 403} or any(marker in msg_lower for marker in AUTH_ERROR_MARKERS)

    if any(marker in msg_lower for marker in STATIC_IP_MARKERS):
        return "DHAN_STATIC_IP_REJECTED", False
    if code in _RATE_LIMIT_CODES or any(marker in msg_lower for marker in RATE_LIMIT_MARKERS):
        return "DHAN_RATE_LIMITED", False
    if code in _ACCESS_DENIED_CODES or any(marker in msg_lower for marker in ACCESS_DENIED_MARKERS):
        return "DHAN_ACCESS_DENIED", False
    if code in _AUTH_ERROR_CODES or code in _AUTH_HTTP_CODES or status in {401, 403}:
        return "DHAN_AUTH_FAILED", True
    if code in _ACCOUNT_ERROR_CODES:
        return "DHAN_ACCOUNT_RESTRICTED", False
    if code in _INVALID_REQUEST_CODES or any(marker in msg_lower for marker in INVALID_REQUEST_MARKERS):
        return "DHAN_INVALID_REQUEST", is_auth
    if code in _NO_DATA_CODES:
        if any(marker in msg_lower for marker in INVALID_REQUEST_MARKERS):
            return "DHAN_INVALID_REQUEST", is_auth
        return "DHAN_NO_DATA", is_auth
    if any(marker in msg_lower for marker in NO_DATA_MARKERS):
        return "DHAN_NO_DATA", is_auth
    if code in _UPSTREAM_ERROR_CODES:
        return "DHAN_UPSTREAM_FAILED", is_auth
    return ("DHAN_AUTH_FAILED" if is_auth else ""), is_auth


def _classify_structured(error_code: str, error_message: str) -> tuple[str, bool]:
    """Classify Dhan errors using documented codes and explicit message families."""
    return _classify_dhan_error(error_code, error_message)


class DhanApiError(RuntimeError):
    def __init__(self, reason: str, message: str, *, auth_failed: bool = False, payload: Any | None = None) -> None:
        super().__init__(message)
        self.reason, self.message, self.auth_failed, self.payload = reason, message, auth_failed, payload


@dataclass(frozen=True, slots=True)
class DhanCredentialSnapshot:
    configured: bool
    client_id: str | None
    access_token: str | None
    expires_at: datetime | None
    token_source: str | None
    last_refreshed_at: datetime | None
    last_profile_checked_at: datetime | None
    last_rest_success_at: datetime | None
    data_plan_status: str | None
    data_valid_until: datetime | None
    last_lease_issued_at: datetime | None
    generation: int
    totp_regeneration_enabled: bool


def _decode_token_expiry(raw: str | None) -> datetime | None:
    if not raw or raw.count(".") < 2:
        return None
    try:
        p = raw.split(".", 2)[1]
        p += "=" * (-len(p) % 4)
        exp = json.loads(base64.urlsafe_b64decode(p)).get("exp")
    except Exception:
        return None
    return datetime.fromtimestamp(exp, timezone.utc) if isinstance(exp, (int, float)) else None

def _parse_ist_datetime(value: str | None) -> datetime | None:
    if not value or not (c := value.strip()):
        return None
    for f in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(c, f).replace(tzinfo=IST).astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(c.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed).astimezone(timezone.utc)

def _ensure_utc(v: datetime | None) -> datetime | None:
    if v is None:
        return None
    return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)

def _totp_code(secret: str, *, for_time: float | None = None) -> str:
    key = base64.b32decode(secret.replace(" ", "").upper(), casefold=True)
    counter = int((time.time() if for_time is None else for_time) // 30)
    d = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = d[-1] & 0x0F
    return f"{(struct.unpack('>I', d[o:o+4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"

def _totp_candidates(secret: str) -> list[str]:
    return _totp_candidates_for_time(secret, for_time=time.time())


def _totp_candidates_for_time(secret: str, *, for_time: float) -> list[str]:
    seen: list[str] = []
    for off in (0, -30, 30, -60, 60):
        c = _totp_code(secret, for_time=for_time + off)
        if c not in seen:
            seen.append(c)
    return seen


def _seconds_until_next_totp_window(*, now: float | None = None, safety_seconds: float = 1.5) -> float:
    current = time.time() if now is None else now
    return max((30 - (current % 30)) + safety_seconds, safety_seconds)


def _endpoint_label(url: str) -> str:
    path = urlsplit(url).path or url
    return path.rsplit("/", 1)[-1] or path


def _totp_error_from_payload(payload: dict[str, Any]) -> DhanApiError:
    error_code, error_message = _extract_error_details(payload)
    message = str(error_message or payload.get("message") or payload)[:500]
    reason, auth_failed = _classify_dhan_error(error_code, message)
    lower = message.lower()
    if not reason and any(marker in lower for marker in TOTP_INVALID_MARKERS):
        reason, auth_failed = "DHAN_TOTP_INVALID", True
    elif any(marker in lower for marker in TOTP_REGEN_RATE_LIMIT_MARKERS):
        reason, auth_failed = "DHAN_RATE_LIMITED", False
    if not reason:
        reason, auth_failed = "DHAN_TOKEN_REGENERATION_FAILED", True
    return DhanApiError(reason, f"TOTP response missing token: {message}", auth_failed=auth_failed, payload=payload)

def _classify(msg: str, status: int = 0) -> tuple[str, bool]:
    return _classify_dhan_error(None, msg, status=status)


class DhanRateLimiter:
    """Thread-safe token bucket rate limiter for Dhan API calls.

    burst_cap limits how many tokens can accumulate during idle periods,
    preventing a burst that exceeds Dhan's short-window limits.
    """

    def __init__(self, rate_per_second: float, capacity: int, *, burst_cap: int | None = None, reserved_capacity: int = 0) -> None:
        self._rate = rate_per_second
        self._capacity = capacity
        self._burst_cap = min(burst_cap, capacity) if burst_cap is not None else capacity
        self._reserved_capacity = min(max(reserved_capacity, 0), self._burst_cap)
        self._tokens = float(self._burst_cap)
        self._last = time.monotonic()
        self._lock = threading.Lock()
        self._op_cooldowns: dict[str, float] = {}  # operation -> last_call_monotonic

    def acquire(
        self,
        timeout: float = 30.0,
        *,
        operation: str | None = None,
        cooldown: float = 0.0,
        priority: str = "normal",
    ) -> bool:
        deadline = time.monotonic() + timeout
        # Per-operation cooldown (e.g., option_chain must wait 3s between calls)
        if operation and cooldown > 0:
            with self._lock:
                last = self._op_cooldowns.get(operation, 0.0)
                wait = last + cooldown - time.monotonic()
                if wait > 0:
                    if wait > (deadline - time.monotonic()):
                        return False
                    time.sleep(wait)
        while True:
            with self._lock:
                now = time.monotonic()
                refill = min(self._burst_cap, self._tokens + (now - self._last) * self._rate)
                self._tokens = refill
                self._last = now
                available = self._tokens if priority in {"critical", "high"} else max(self._tokens - self._reserved_capacity, 0.0)
                if available >= 1.0:
                    self._tokens -= 1.0
                    if operation:
                        self._op_cooldowns[operation] = now
                    return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.05, remaining))


_api_rate_limiter = DhanRateLimiter(
    rate_per_second=max(settings.dhan_api_rate_limit_per_minute, 1) / 60.0,
    capacity=max(settings.dhan_api_rate_limit_per_minute, 1),
    burst_cap=5,  # Never burst more than 5 requests even after idle
    reserved_capacity=3,  # Preserve enough headroom for profile -> regen -> profile recovery.
)


class DhanCredentialService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._renewal_lock = threading.Lock()
        self._initialized = False
        self._scheduler_task: asyncio.Task | None = None
        self._scheduler_stop: asyncio.Event | None = None
        self._client_id: str | None = None
        self._access_token: str | None = None
        self._expires_at: datetime | None = None
        self._token_source: str | None = None
        self._last_refreshed_at: datetime | None = None
        self._last_profile_checked_at: datetime | None = None
        self._last_lease_issued_at: datetime | None = None
        self._last_rest_success_at: datetime | None = None
        self._data_plan_status: str | None = None
        self._data_valid_until: datetime | None = None
        self._generation = 0
        self._dead_generation: int | None = None
        self._last_totp_success_at: float = 0.0
        self._next_totp_attempt_at: float = 0.0
        self._global_backoff_until: float | None = None
        self._backoff_count: int = 0

    def initialize(self, *, force_reload: bool = False) -> None:
        with self._lock:
            if self._initialized and not force_reload:
                return
            self._load_from_storage()
            self._initialized = True

    def reset_runtime_state(self) -> None:
        with self._lock:
            self._initialized = False
            self._generation = 0
            self._client_id = self._access_token = self._expires_at = self._token_source = None
            self._last_refreshed_at = self._last_profile_checked_at = self._last_lease_issued_at = None
            self._last_rest_success_at = self._data_plan_status = self._data_valid_until = None
            self._dead_generation = None
            self._last_totp_success_at = 0.0
            self._next_totp_attempt_at = 0.0
            self._global_backoff_until = None
            self._backoff_count = 0

    def snapshot(self) -> DhanCredentialSnapshot:
        self.initialize()
        with self._lock:
            return DhanCredentialSnapshot(
                configured=bool(self._client_id and self._access_token), client_id=self._client_id,
                access_token=self._access_token, expires_at=self._expires_at, token_source=self._token_source,
                last_refreshed_at=self._last_refreshed_at, last_profile_checked_at=self._last_profile_checked_at,
                last_rest_success_at=self._last_rest_success_at, data_plan_status=self._data_plan_status,
                data_valid_until=self._data_valid_until, last_lease_issued_at=self._last_lease_issued_at,
                generation=self._generation, totp_regeneration_enabled=bool(settings.dhan_pin and settings.dhan_totp_secret),
            )

    def configured(self) -> bool:
        return self.snapshot().configured

    def create_client(self) -> Dhanhq:
        s = self.snapshot()
        if not s.client_id or not s.access_token:
            raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan credentials are not configured")
        return Dhanhq(s.client_id, s.access_token)

    def _generation_is_dead(self, generation: int) -> bool:
        with self._lock:
            return self._dead_generation == generation

    def _mark_generation_dead(self, generation: int) -> None:
        with self._lock:
            if generation == self._generation:
                self._dead_generation = generation

    @staticmethod
    def _planned_renewal_due(snapshot: DhanCredentialSnapshot, now: datetime) -> bool:
        return bool(
            snapshot.expires_at
            and (snapshot.expires_at - now).total_seconds()
            <= max(settings.dhan_token_renewal_lead_seconds, 60)
        )

    @staticmethod
    def _assert_data_plan_active(snapshot: DhanCredentialSnapshot, now: datetime) -> None:
        if snapshot.data_plan_status and snapshot.data_plan_status.lower() != "active":
            raise DhanApiError("DATA_PLAN_INACTIVE", f"Dhan data plan is {snapshot.data_plan_status}")
        if snapshot.data_valid_until and snapshot.data_valid_until < now:
            raise DhanApiError("DATA_PLAN_INACTIVE", "Dhan market-data entitlement has expired")

    def ensure_token_fresh(self, force_profile: bool = False, *, allow_planned_renewal: bool = False) -> bool:
        self.initialize()
        snap, now = self.snapshot(), datetime.now(timezone.utc)
        if not snap.client_id:
            raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan client id is not configured")
        if not snap.access_token:
            return self._regenerate_via_totp(reason="missing-access-token")
        needs_profile = (
            self._generation_is_dead(snap.generation)
            or force_profile
            or not snap.last_profile_checked_at
            or (now - snap.last_profile_checked_at).total_seconds() >= max(settings.dhan_profile_check_seconds, 60)
        )
        needs_renewal = allow_planned_renewal and self._planned_renewal_due(snap, now)
        if not needs_profile and not needs_renewal:
            return False
        with self._renewal_lock:
            snap = self.snapshot()
            now = datetime.now(timezone.utc)
            needs_profile = (
                self._generation_is_dead(snap.generation)
                or force_profile
                or not snap.last_profile_checked_at
                or (now - snap.last_profile_checked_at).total_seconds() >= max(settings.dhan_profile_check_seconds, 60)
            )
            needs_renewal = allow_planned_renewal and self._planned_renewal_due(snap, now)
            if not snap.access_token:
                return self._regenerate_via_totp_inner(reason="missing-access-token")
            if needs_profile:
                try:
                    profile = self._fetch_profile(snap.client_id, snap.access_token)
                except DhanApiError as exc:
                    if exc.auth_failed:
                        self._mark_generation_dead(snap.generation)
                        return self._regenerate_via_totp_inner(reason="profile-check-failed")
                    raise
                self._record_profile(profile)
                snap = self.snapshot()
                now = datetime.now(timezone.utc)
            self._assert_data_plan_active(snap, now)
            if allow_planned_renewal and self._planned_renewal_due(snap, now):
                return self._renew_active_token_inner(reason="planned-renewal")
            return False

    # Dhan enforces per-endpoint cooldowns; option_chain is 1 req per 3 seconds
    _OP_COOLDOWNS: dict[str, float] = {"option_chain": 3.0}

    @staticmethod
    def _budget_priority(operation_name: str) -> str:
        if operation_name in _CRITICAL_BUDGET_OPERATIONS:
            return "critical"
        if operation_name in _HIGH_PRIORITY_BUDGET_OPERATIONS:
            return "high"
        return "normal"

    def _acquire_budget(self, operation_name: str) -> None:
        priority = self._budget_priority(operation_name)
        if priority != "critical" and self._global_backoff_until:
            now = time.monotonic()
            if now < self._global_backoff_until:
                remaining = self._global_backoff_until - now
                raise DhanApiError("DHAN_RATE_LIMITED", f"{operation_name} blocked: global backoff active ({remaining:.0f}s remaining)")
        cooldown = self._OP_COOLDOWNS.get(operation_name, 0.0)
        if not _api_rate_limiter.acquire(timeout=30.0, operation=operation_name, cooldown=cooldown, priority=priority):
            raise DhanApiError("DHAN_RATE_LIMITED", f"{operation_name} blocked: rate limiter exhausted")

    def call(self, operation_name: str, fn: Callable[[Dhanhq], T], *, allow_auth_retry: bool = True) -> T:
        self.ensure_token_fresh(allow_planned_renewal=True)
        self._acquire_budget(operation_name)
        for attempt in (1, 2):
            attempt_snapshot = self.snapshot()
            if not attempt_snapshot.client_id or not attempt_snapshot.access_token:
                raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan credentials are not configured")
            try:
                result = fn(Dhanhq(attempt_snapshot.client_id, attempt_snapshot.access_token))
            except Exception as exc:
                raise DhanApiError("DHAN_TRANSPORT_FAILED", f"{operation_name} request failed: {type(exc).__name__}: {exc}") from exc
            try:
                data = self._unwrap_sdk_result(operation_name, result)
            except DhanApiError as exc:
                if exc.reason == "DHAN_RATE_LIMITED":
                    self._apply_global_backoff()
                if exc.auth_failed and allow_auth_retry and attempt == 1:
                    self._mark_generation_dead(attempt_snapshot.generation)
                    if self.snapshot().generation != attempt_snapshot.generation:
                        continue
                    self._regenerate_via_totp(reason=f"{operation_name}-auth-retry")
                    continue
                raise
            with self._lock:
                self._last_rest_success_at = datetime.now(timezone.utc)
                self._backoff_count = 0
                self._global_backoff_until = None
            return data

    def _apply_global_backoff(self) -> None:
        self._backoff_count += 1
        backoff_seconds = min(60 * (2 ** (self._backoff_count - 1)), max(settings.dhan_rate_limit_backoff_seconds, 60))
        self._global_backoff_until = time.monotonic() + backoff_seconds
        logger.warning("Dhan global backoff activated: %ds (consecutive=%d)", backoff_seconds, self._backoff_count)

    def clear_backoff(self) -> None:
        if self._global_backoff_until:
            self._backoff_count = 0
            self._global_backoff_until = None

    def issue_lease(self) -> DhanCredentialSnapshot:
        # Internal consumers need a broker-validated token, not just a token
        # that looked valid some minutes ago.
        self.ensure_token_fresh(force_profile=True, allow_planned_renewal=True)
        snap = self.snapshot()
        if not snap.client_id or not snap.access_token:
            raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan credentials are not configured")
        if snap.data_plan_status and snap.data_plan_status.lower() != "active":
            raise DhanApiError("DATA_PLAN_INACTIVE", f"Dhan data plan is {snap.data_plan_status}")
        with self._lock:
            self._last_lease_issued_at = datetime.now(timezone.utc)
        self._persist_runtime_state()
        return self.snapshot()

    def scheduled_preopen_rotation(self) -> bool:
        self.initialize()
        return self.ensure_token_fresh(force_profile=True, allow_planned_renewal=True)

    async def start_background_tasks(self) -> None:
        if self._scheduler_task:
            return
        self._scheduler_stop = asyncio.Event()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop_background_tasks(self) -> None:
        if not self._scheduler_task:
            return
        if self._scheduler_stop:
            self._scheduler_stop.set()
        self._scheduler_task.cancel()
        try:
            await self._scheduler_task
        except asyncio.CancelledError:
            pass
        self._scheduler_task = self._scheduler_stop = None

    # -- Storage --

    def _load_from_storage(self) -> None:
        env_cid = (settings.dhan_client_id or "").strip() or None
        env_tok = (settings.dhan_access_token or "").strip() or None
        db = SessionLocal()
        try:
            rec = db.query(ServiceCredential).filter(ServiceCredential.provider == "dhan").first()
        finally:
            db.close()
        if rec and rec.access_token:
            cid, tok, src = rec.client_id, rec.access_token, rec.token_source or "db"
            exp = _ensure_utc(rec.expires_at) or _decode_token_expiry(tok)
            ref, val = _ensure_utc(rec.last_refreshed_at), _ensure_utc(rec.last_validated_at)
        elif env_tok:
            cid, tok, src = env_cid, env_tok, "env"
            exp, ref, val = _decode_token_expiry(env_tok), None, None
        else:
            cid, tok, src, exp, ref, val = env_cid, None, None, None, None, None
        with self._lock:
            self._client_id, self._access_token, self._expires_at = cid, tok, exp
            self._token_source, self._last_refreshed_at, self._last_profile_checked_at = src, ref, val
            self._last_lease_issued_at = _ensure_utc(rec.last_lease_issued_at) if rec else None
            self._data_plan_status = rec.data_plan_status if rec else None
            self._data_valid_until = _ensure_utc(rec.data_valid_until) if rec else None
            self._generation = int(rec.generation or 0) if rec else 0
        if cid and tok:
            self._persist_runtime_state()

    def _persist_runtime_state(self) -> None:
        with self._lock:
            cid, tok, exp = self._client_id, self._access_token, self._expires_at
            src, gen = self._token_source, self._generation
            ref, val = self._last_refreshed_at, self._last_profile_checked_at
            dp, dv, lei = self._data_plan_status, self._data_valid_until, self._last_lease_issued_at
        if not cid or not tok:
            return
        db = SessionLocal()
        try:
            r = db.query(ServiceCredential).filter(ServiceCredential.provider == "dhan").first()
            if not r:
                r = ServiceCredential(provider="dhan", client_id=cid, access_token=tok)
            r.client_id, r.access_token, r.expires_at = cid, tok, exp
            r.token_source, r.generation = src or "authority", gen
            r.last_refreshed_at, r.last_validated_at = ref, val
            r.data_plan_status, r.data_valid_until, r.last_lease_issued_at = dp, dv, lei
            db.add(r)
            db.commit()
        finally:
            db.close()

    def _apply_new_token(self, *, client_id: str, access_token: str, expires_at: datetime | None,
                         token_source: str, refreshed_at: datetime | None) -> None:
        with self._lock:
            changed = access_token != self._access_token
            self._client_id, self._access_token = client_id, access_token
            self._expires_at, self._token_source, self._last_refreshed_at = expires_at, token_source, refreshed_at
            if changed:
                self._generation += 1
            self._dead_generation = None
            self._next_totp_attempt_at = 0.0
        self._persist_runtime_state()

    def _record_profile(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._last_profile_checked_at = datetime.now(timezone.utc)
            self._data_plan_status = str(payload.get("dataPlan") or "").strip() or None
            self._data_valid_until = _parse_ist_datetime(str(payload.get("dataValidity") or ""))
            exp = _parse_ist_datetime(str(payload.get("tokenValidity") or ""))
            if exp:
                self._expires_at = exp
            self._dead_generation = None
        self._persist_runtime_state()

    # -- Dhan API --

    def _fetch_profile(self, client_id: str, access_token: str) -> dict[str, Any]:
        return self._request_json(
            "GET", f"{DHAN_API_BASE}/profile",
            headers={"Accept": "application/json", "Content-Type": "application/json",
                     "access-token": access_token, "client-id": client_id, "dhanClientId": client_id},
            budget_operation="profile",
        )

    def _renew_active_token_inner(self, *, reason: str) -> bool:
        """Refresh an active token. Caller MUST already hold _renewal_lock."""
        snap = self.snapshot()
        if not snap.client_id or not snap.access_token:
            return self._regenerate_via_totp_inner(reason=f"{reason}-missing-token")
        try:
            resp = self._request_json(
                "GET",
                f"{DHAN_API_BASE}/RenewToken",
                headers={
                    "Accept": "application/json",
                    "access-token": snap.access_token,
                    "dhanClientId": snap.client_id,
                    "client-id": snap.client_id,
                },
                budget_operation="renew_token",
            )
        except DhanApiError as exc:
            logger.warning("Active token renewal failed via %s: %s", reason, exc.reason or exc.message)
            if exc.auth_failed:
                self._mark_generation_dead(snap.generation)
            return self._regenerate_via_totp_inner(reason=f"{reason}-totp-fallback")
        next_tok = str(resp.get("accessToken") or resp.get("token") or "").strip()
        if not next_tok:
            logger.warning("Active token renewal missing token via %s; falling back to TOTP", reason)
            return self._regenerate_via_totp_inner(reason=f"{reason}-totp-fallback")
        exp = _parse_ist_datetime(str(resp.get("expiryTime") or "")) or _decode_token_expiry(next_tok)
        self._apply_new_token(
            client_id=snap.client_id,
            access_token=next_tok,
            expires_at=exp,
            token_source="renew",
            refreshed_at=datetime.now(timezone.utc),
        )
        logger.info("Renewed active Dhan token for %s via %s", snap.client_id, reason)
        try:
            self._record_profile(self._fetch_profile(snap.client_id, next_tok))
        except DhanApiError:
            logger.warning("Profile fetch failed after active token renewal — token saved, profile updates on next check")
        return True

    def _regenerate_via_totp(self, *, reason: str, force: bool = False) -> bool:
        """Acquire renewal lock and regenerate. Use _regenerate_via_totp_inner if lock is already held."""
        cid = (self.snapshot().client_id or settings.dhan_client_id or "").strip()
        pin, secret = (settings.dhan_pin or "").strip(), (settings.dhan_totp_secret or "").strip()
        if not cid or not pin or not secret:
            raise DhanApiError("DHAN_TOKEN_RENEWAL_FAILED", "TOTP regeneration not configured", auth_failed=True)
        gen_before = self.snapshot().generation
        with self._renewal_lock:
            if not force and self.snapshot().generation != gen_before:
                return True
            return self._regenerate_via_totp_inner(reason=reason)

    def _attempt_totp_regeneration(self, *, client_id: str, pin: str, secret: str, at_time: float) -> tuple[str, dict[str, Any] | None, DhanApiError | None]:
        next_tok = ""
        payload: dict[str, Any] | None = None
        last_error: DhanApiError | None = None
        for totp in _totp_candidates_for_time(secret, for_time=at_time):
            try:
                resp = self._request_json(
                    "POST",
                    f"{DHAN_AUTH_BASE}/generateAccessToken",
                    params={"dhanClientId": client_id, "pin": pin, "totp": totp},
                    budget_operation="generate_access_token",
                )
            except DhanApiError as exc:
                last_error = exc
                if exc.reason == "DHAN_RATE_LIMITED":
                    return "", None, exc
                continue
            token = str(resp.get("accessToken") or resp.get("token") or "").strip()
            if token:
                return token, resp, None
            last_error = _totp_error_from_payload(resp)
            if last_error.reason == "DHAN_RATE_LIMITED":
                return "", None, last_error
        return next_tok, payload, last_error

    def _regenerate_via_totp_inner(self, *, reason: str) -> bool:
        """Do the actual TOTP regeneration. Caller MUST already hold _renewal_lock."""
        cid = (self.snapshot().client_id or settings.dhan_client_id or "").strip()
        pin, secret = (settings.dhan_pin or "").strip(), (settings.dhan_totp_secret or "").strip()
        if not cid or not pin or not secret:
            raise DhanApiError("DHAN_TOKEN_RENEWAL_FAILED", "TOTP regeneration not configured", auth_failed=True)
        attempts_remaining = 2
        last_err: DhanApiError | None = None
        next_tok = ""
        pay: dict[str, Any] | None = None
        while attempts_remaining > 0:
            now_monotonic = time.monotonic()
            if self._next_totp_attempt_at > now_monotonic:
                wait_seconds = self._next_totp_attempt_at - now_monotonic
                logger.warning("Waiting %.1fs before retrying Dhan TOTP regeneration", wait_seconds)
                time.sleep(wait_seconds)
            next_tok, pay, last_err = self._attempt_totp_regeneration(
                client_id=cid,
                pin=pin,
                secret=secret,
                at_time=time.time(),
            )
            if next_tok:
                break
            attempts_remaining -= 1
            if not last_err:
                break
            if last_err.reason == "DHAN_RATE_LIMITED":
                next_allowed_at = self._last_totp_success_at + 130.0 if self._last_totp_success_at else time.monotonic() + 130.0
                self._next_totp_attempt_at = max(self._next_totp_attempt_at, next_allowed_at)
                continue
            if last_err.reason == "DHAN_TOTP_INVALID" and attempts_remaining > 0:
                self._next_totp_attempt_at = time.monotonic() + _seconds_until_next_totp_window()
                continue
            break
        if not next_tok or not pay:
            raise last_err or DhanApiError("DHAN_TOKEN_REGENERATION_FAILED", "TOTP regeneration failed", auth_failed=True)
        self._last_totp_success_at = time.monotonic()
        # Apply token first — if profile fetch fails, the token is still saved
        exp = _parse_ist_datetime(str(pay.get("expiryTime") or "")) or _decode_token_expiry(next_tok)
        self._apply_new_token(client_id=cid, access_token=next_tok, expires_at=exp,
                              token_source="totp", refreshed_at=datetime.now(timezone.utc))
        logger.info("Regenerated Dhan token for %s via %s", cid, reason)
        try:
            self._record_profile(self._fetch_profile(cid, next_tok))
        except DhanApiError:
            logger.warning("Profile fetch failed after token regen — token saved, profile updates on next check")
        return True

    def _request_json(self, method: str, url: str, *, budget_operation: str | None = None, **kwargs: Any) -> dict[str, Any]:
        if budget_operation:
            self._acquire_budget(budget_operation)
        kwargs.setdefault("timeout", settings.dhan_http_timeout_seconds)
        endpoint = _endpoint_label(url)
        try:
            response = httpx.request(method, url, **kwargs)
        except Exception as exc:
            raise DhanApiError("DHAN_TRANSPORT_FAILED", f"Dhan request to {endpoint} failed: {type(exc).__name__}: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise DhanApiError("DHAN_REQUEST_FAILED", f"Dhan {endpoint} invalid JSON: {response.text[:300]}",
                               auth_failed=response.status_code in {401, 403}) from exc
        if response.status_code >= 400:
            error_code, error_message = _extract_error_details(payload)
            msg = error_message or str(payload)[:500]
            reason, is_auth = _classify_dhan_error(error_code, msg, status=response.status_code)
            raise DhanApiError(reason or "DHAN_REQUEST_FAILED", f"{endpoint} failed: {msg}", auth_failed=is_auth, payload=payload)
        return payload if isinstance(payload, dict) else {}

    def _unwrap_sdk_result(self, op: str, result: Any) -> Any:
        if not isinstance(result, dict):
            raise DhanApiError("DHAN_PROTOCOL_FAILED", f"{op} returned {type(result).__name__}, expected dict", payload=result)
        if str(result.get("status") or "").lower() == "success":
            return result.get("data")

        error_code, error_message = _extract_error_details(result)
        data = result.get("data")
        msg = error_message or str(data)[:500] or f"{op} failed"
        reason, auth = _classify_structured(error_code, error_message)
        raise DhanApiError(reason or "DHAN_UPSTREAM_FAILED", f"{op} failed: {msg}", auth_failed=auth, payload=result)

    # -- Scheduler --

    @staticmethod
    def _next_rotation_time(now: datetime | None = None) -> datetime:
        cur = now or datetime.now(timezone.utc)
        t = cur.replace(hour=3, minute=20, second=0, microsecond=0)
        return t if cur < t else t + timedelta(days=1)

    async def _scheduler_loop(self) -> None:
        while True:
            stop = self._scheduler_stop
            if stop is None:
                return
            wait = max((self._next_rotation_time() - datetime.now(timezone.utc)).total_seconds(), 1)
            try:
                await asyncio.wait_for(stop.wait(), timeout=wait)
                return
            except asyncio.TimeoutError:
                pass
            try:
                rotated = await asyncio.to_thread(self.scheduled_preopen_rotation)
                logger.info("Scheduled rotation completed (rotated=%s)", rotated)
            except Exception:
                logger.exception("Scheduled rotation failed")


dhan_credential_service = DhanCredentialService()
