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

# Structured Dhan error code classification (used by _unwrap_sdk_result for SDK responses)
_AUTH_ERROR_CODES = {"DH-901", "DH-903"}
_RATE_LIMIT_CODES = {"DH-904", "805"}
_AUTH_HTTP_CODES = {"401", "403"}


def _classify_structured(error_code: str, error_message: str) -> tuple[str, bool]:
    """Classify Dhan errors using structured error codes, not substring matching."""
    code_upper = error_code.upper()
    msg_lower = error_message.lower()

    # Rate limiting — check error code first, then message
    if code_upper in _RATE_LIMIT_CODES or code_upper == "429":
        return "DHAN_RATE_LIMITED", False
    if "too many request" in msg_lower:
        return "DHAN_RATE_LIMITED", False

    # Auth errors — check error code first, then message
    if code_upper in _AUTH_ERROR_CODES or code_upper in _AUTH_HTTP_CODES:
        return "DHAN_AUTH_FAILED", True
    if any(m in msg_lower for m in ("authentication failed", "token invalid", "invalid token", "invalid jwt", "unauthorized")):
        return "DHAN_AUTH_FAILED", True

    # Static IP
    if any(m in msg_lower for m in ("static ip", "whitelisted ip", "ip mismatch")):
        return "DHAN_STATIC_IP_REJECTED", False

    return "", False


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
    now, seen = time.time(), []
    for off in (0, -30, 30):
        c = _totp_code(secret, for_time=now + off)
        if c not in seen:
            seen.append(c)
    return seen

def _classify(msg: str, status: int = 0) -> tuple[str, bool]:
    low = msg.lower()
    is_auth = status in {401, 403} or any(m in low for m in ("authentication failed", "token invalid", "invalid token", "invalid jwt", "unauthorized"))
    if any(m in low for m in ("too many request", "too many requests")) or status == 429:
        return "DHAN_RATE_LIMITED", is_auth
    if any(m in low for m in STATIC_IP_MARKERS):
        return "DHAN_STATIC_IP_REJECTED", is_auth
    return ("DHAN_AUTH_FAILED" if is_auth else ""), is_auth


class DhanRateLimiter:
    """Thread-safe token bucket rate limiter for Dhan API calls.

    burst_cap limits how many tokens can accumulate during idle periods,
    preventing a burst that exceeds Dhan's short-window limits.
    """

    def __init__(self, rate_per_second: float, capacity: int, *, burst_cap: int | None = None) -> None:
        self._rate = rate_per_second
        self._capacity = capacity
        self._burst_cap = min(burst_cap, capacity) if burst_cap is not None else capacity
        self._tokens = float(self._burst_cap)
        self._last = time.monotonic()
        self._lock = threading.Lock()
        self._op_cooldowns: dict[str, float] = {}  # operation -> last_call_monotonic

    def acquire(self, timeout: float = 30.0, *, operation: str | None = None, cooldown: float = 0.0) -> bool:
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
                if self._tokens >= 1.0:
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
        self._last_totp_generation_at: float = 0.0
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

    def ensure_token_fresh(self, force_profile: bool = False) -> bool:
        self.initialize()
        snap, now = self.snapshot(), datetime.now(timezone.utc)
        if not snap.client_id:
            raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan client id is not configured")
        if not snap.access_token:
            return self._regenerate_via_totp(reason="missing-access-token")
        needs_profile = (force_profile or not snap.last_profile_checked_at
                         or (now - snap.last_profile_checked_at).total_seconds() >= max(settings.dhan_profile_check_seconds, 60))
        needs_renewal = bool(snap.expires_at and (snap.expires_at - now).total_seconds() <= max(settings.dhan_token_renewal_lead_seconds, 60))
        if needs_profile:
            # Serialize profile checks under the renewal lock. Without this,
            # concurrent threads can each trigger a profile check with the same
            # token, then one thread's TOTP regen invalidates the token the
            # other threads are using, causing a cascade of regenerations.
            with self._renewal_lock:
                # Re-check under lock — another thread may have already done the profile check
                snap = self.snapshot()
                now = datetime.now(timezone.utc)
                still_needs = (force_profile or not snap.last_profile_checked_at
                               or (now - snap.last_profile_checked_at).total_seconds() >= max(settings.dhan_profile_check_seconds, 60))
                if still_needs and snap.access_token:
                    try:
                        profile = self._fetch_profile(snap.client_id, snap.access_token)
                    except DhanApiError as exc:
                        needs_renewal = bool(snap.expires_at and (snap.expires_at - now).total_seconds() <= max(settings.dhan_token_renewal_lead_seconds, 60))
                        if exc.auth_failed or needs_renewal:
                            # Already hold _renewal_lock — call inner regen directly
                            return self._regenerate_via_totp_inner(reason="profile-check-failed")
                        raise
                    self._record_profile(profile)
                snap = self.snapshot()
            if snap.data_plan_status and snap.data_plan_status.lower() != "active":
                raise DhanApiError("DATA_PLAN_INACTIVE", f"Dhan data plan is {snap.data_plan_status}")
            if snap.data_valid_until and snap.data_valid_until < now:
                raise DhanApiError("DATA_PLAN_INACTIVE", "Dhan market-data entitlement has expired")
            needs_renewal = bool(snap.expires_at and (snap.expires_at - now).total_seconds() <= max(settings.dhan_token_renewal_lead_seconds, 60))
        return self._regenerate_via_totp(reason="scheduled-renewal") if needs_renewal else False

    # Dhan enforces per-endpoint cooldowns; option_chain is 1 req per 3 seconds
    _OP_COOLDOWNS: dict[str, float] = {"option_chain": 3.0}

    def call(self, operation_name: str, fn: Callable[[Dhanhq], T], *, allow_auth_retry: bool = True) -> T:
        if self._global_backoff_until:
            now = time.monotonic()
            if now < self._global_backoff_until:
                remaining = self._global_backoff_until - now
                raise DhanApiError("DHAN_RATE_LIMITED", f"{operation_name} blocked: global backoff active ({remaining:.0f}s remaining)")
        cooldown = self._OP_COOLDOWNS.get(operation_name, 0.0)
        if not _api_rate_limiter.acquire(timeout=30.0, operation=operation_name, cooldown=cooldown):
            raise DhanApiError("DHAN_RATE_LIMITED", f"{operation_name} blocked: rate limiter exhausted")
        self.ensure_token_fresh()
        for attempt in (1, 2):
            try:
                result = fn(self.create_client())
            except Exception as exc:
                raise DhanApiError("DHAN_TRANSPORT_FAILED", f"{operation_name} request failed: {type(exc).__name__}: {exc}") from exc
            try:
                data = self._unwrap_sdk_result(operation_name, result)
            except DhanApiError as exc:
                if exc.reason == "DHAN_RATE_LIMITED":
                    self._apply_global_backoff()
                if exc.auth_failed and allow_auth_retry and attempt == 1:
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
        self.ensure_token_fresh()
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
        return self._regenerate_via_totp(reason="scheduled-rotation", force=True)

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
        self._persist_runtime_state()

    def _record_profile(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._last_profile_checked_at = datetime.now(timezone.utc)
            self._data_plan_status = str(payload.get("dataPlan") or "").strip() or None
            self._data_valid_until = _parse_ist_datetime(str(payload.get("dataValidity") or ""))
            exp = _parse_ist_datetime(str(payload.get("tokenValidity") or ""))
            if exp:
                self._expires_at = exp
        self._persist_runtime_state()

    # -- Dhan API --

    def _fetch_profile(self, client_id: str, access_token: str) -> dict[str, Any]:
        return self._request_json(
            "GET", f"{DHAN_API_BASE}/profile",
            headers={"Accept": "application/json", "Content-Type": "application/json",
                     "access-token": access_token, "client-id": client_id, "dhanClientId": client_id},
        )

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

    def _regenerate_via_totp_inner(self, *, reason: str) -> bool:
        """Do the actual TOTP regeneration. Caller MUST already hold _renewal_lock."""
        cid = (self.snapshot().client_id or settings.dhan_client_id or "").strip()
        pin, secret = (settings.dhan_pin or "").strip(), (settings.dhan_totp_secret or "").strip()
        if not cid or not pin or not secret:
            raise DhanApiError("DHAN_TOKEN_RENEWAL_FAILED", "TOTP regeneration not configured", auth_failed=True)
        # Dhan rate-limits generateAccessToken to once per 2 minutes
        elapsed = time.time() - self._last_totp_generation_at
        if elapsed < 130:
            s = self.snapshot()
            if s.access_token and s.expires_at and s.expires_at > datetime.now(timezone.utc):
                logger.info("Skipping TOTP regen (%.0fs cooldown, token valid)", 130 - elapsed)
                return False
            logger.warning("TOTP rate-limited, token expired; waiting %.0fs", 130 - elapsed)
            time.sleep(130 - elapsed)
        self._last_totp_generation_at = time.time()
        next_tok, pay, last_err = "", None, None
        for totp in _totp_candidates(secret):
            try:
                resp = self._request_json("POST", f"{DHAN_AUTH_BASE}/generateAccessToken",
                                          params={"dhanClientId": cid, "pin": pin, "totp": totp})
            except DhanApiError as e:
                last_err = e
                continue
            t = str(resp.get("accessToken") or resp.get("token") or "").strip()
            if t:
                next_tok, pay = t, resp
                break
            last_err = DhanApiError("DHAN_TOKEN_REGENERATION_FAILED",
                                    f"TOTP response missing token: {str(resp)[:500]}", auth_failed=True, payload=resp)
        if not next_tok:
            raise last_err or DhanApiError("DHAN_TOKEN_REGENERATION_FAILED", "TOTP regeneration failed", auth_failed=True)
        self._last_totp_generation_at = time.time()
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

    def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("timeout", settings.dhan_http_timeout_seconds)
        try:
            response = httpx.request(method, url, **kwargs)
        except Exception as exc:
            raise DhanApiError("DHAN_TRANSPORT_FAILED", f"Dhan request to {url} failed: {type(exc).__name__}: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise DhanApiError("DHAN_REQUEST_FAILED", f"Dhan {url} invalid JSON: {response.text[:300]}",
                               auth_failed=response.status_code in {401, 403}) from exc
        if response.status_code >= 400:
            msg = str(payload)[:500]
            reason, is_auth = _classify(msg, response.status_code)
            raise DhanApiError(reason or "DHAN_REQUEST_FAILED", f"{url} failed: {msg}", auth_failed=is_auth, payload=payload)
        return payload if isinstance(payload, dict) else {}

    def _unwrap_sdk_result(self, op: str, result: Any) -> Any:
        if not isinstance(result, dict):
            raise DhanApiError("DHAN_PROTOCOL_FAILED", f"{op} returned {type(result).__name__}, expected dict", payload=result)
        if str(result.get("status") or "").lower() == "success":
            return result.get("data")

        # Extract structured error info from SDK response
        remarks = result.get("remarks")
        data = result.get("data")
        error_code = ""
        error_message = ""

        if isinstance(remarks, dict):
            error_code = str(remarks.get("error_code") or "").strip()
            error_message = str(remarks.get("error_message") or "").strip()
        elif isinstance(remarks, str):
            error_message = remarks

        if isinstance(data, dict):
            error_code = error_code or str(data.get("errorCode") or "").strip()
            error_message = error_message or str(data.get("errorMessage") or "").strip()

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
