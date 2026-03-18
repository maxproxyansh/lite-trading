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
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any, Callable, TypeVar

import httpx
from dhanhq import dhanhq as Dhanhq

from config import get_settings
from database import SessionLocal
from market_hours import IST, holiday_name
from models import ServiceCredential


settings = get_settings()
logger = logging.getLogger("lite.dhan.credentials")
T = TypeVar("T")
DHAN_API_BASE = "https://api.dhan.co/v2"
DHAN_AUTH_BASE = "https://auth.dhan.co/app"
AUTH_ERROR_MARKERS = (
    "authentication failed",
    "token invalid",
    "invalid token",
    "invalid jwt",
    "unauthorized",
    "401",
)
RATE_LIMIT_MARKERS = ("too many request", "too many requests", "429", "805")
STATIC_IP_MARKERS = ("static ip", "whitelisted ip", "ip mismatch")


class DhanApiError(RuntimeError):
    def __init__(
        self,
        reason: str,
        message: str,
        *,
        auth_failed: bool = False,
        payload: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.auth_failed = auth_failed
        self.payload = payload


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


def _decode_token_expiry(raw_token: str | None) -> datetime | None:
    if not raw_token or raw_token.count(".") < 2:
        return None
    try:
        payload = raw_token.split(".", 2)[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:  # noqa: BLE001
        return None
    exp = data.get("exp")
    if not isinstance(exp, (int, float)):
        return None
    return datetime.fromtimestamp(exp, timezone.utc)


def _parse_ist_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    for parser in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(candidate, parser).replace(tzinfo=IST).astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed.astimezone(timezone.utc)


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _extract_error_text(payload: Any) -> str:
    values: list[str] = []

    def visit(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            stripped = node.strip()
            if stripped:
                values.append(stripped)
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and key.strip():
                    values.append(key.strip())
                visit(value)
            return
        if isinstance(node, (list, tuple, set)):
            for item in node:
                visit(item)
            return
        values.append(str(node))

    visit(payload)
    joined = " | ".join(dict.fromkeys(values))
    return joined[:500]


def _totp_code(secret: str, *, for_time: float | None = None) -> str:
    normalized = secret.replace(" ", "").upper()
    key = base64.b32decode(normalized, casefold=True)
    timestamp = time.time() if for_time is None else for_time
    counter = int(timestamp // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1_000_000:06d}"


def _totp_candidates(secret: str) -> list[str]:
    current_time = time.time()
    candidates: list[str] = []
    for offset in (0, -30, 30):
        code = _totp_code(secret, for_time=current_time + offset)
        if code not in candidates:
            candidates.append(code)
    return candidates


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

    def initialize(self, *, force_reload: bool = False) -> None:
        with self._lock:
            if self._initialized and not force_reload:
                return
            self._initialized = True
        self._load_from_storage()

    def reset_runtime_state(self) -> None:
        with self._lock:
            self._initialized = False
            self._client_id = None
            self._access_token = None
            self._expires_at = None
            self._token_source = None
            self._last_refreshed_at = None
            self._last_profile_checked_at = None
            self._last_lease_issued_at = None
            self._last_rest_success_at = None
            self._data_plan_status = None
            self._data_valid_until = None
            self._generation = 0

    def snapshot(self) -> DhanCredentialSnapshot:
        self.initialize()
        with self._lock:
            return DhanCredentialSnapshot(
                configured=bool(self._client_id and self._access_token),
                client_id=self._client_id,
                access_token=self._access_token,
                expires_at=self._expires_at,
                token_source=self._token_source,
                last_refreshed_at=self._last_refreshed_at,
                last_profile_checked_at=self._last_profile_checked_at,
                last_rest_success_at=self._last_rest_success_at,
                data_plan_status=self._data_plan_status,
                data_valid_until=self._data_valid_until,
                last_lease_issued_at=self._last_lease_issued_at,
                generation=self._generation,
                totp_regeneration_enabled=bool(settings.dhan_pin and settings.dhan_totp_secret),
            )

    def configured(self) -> bool:
        return self.snapshot().configured

    def create_client(self) -> Dhanhq:
        snapshot = self.snapshot()
        if not snapshot.client_id or not snapshot.access_token:
            raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan credentials are not configured")
        return Dhanhq(snapshot.client_id, snapshot.access_token)

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
        self._scheduler_task = None
        self._scheduler_stop = None

    def issue_lease(self) -> DhanCredentialSnapshot:
        self.ensure_token_fresh()
        snapshot = self.snapshot()
        if not snapshot.client_id or not snapshot.access_token:
            raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan credentials are not configured")
        if snapshot.data_plan_status and snapshot.data_plan_status.lower() != "active":
            raise DhanApiError(
                "DATA_PLAN_INACTIVE",
                f"Dhan data plan is {snapshot.data_plan_status}",
            )
        now = datetime.now(timezone.utc)
        with self._lock:
            self._last_lease_issued_at = now
        self._persist_runtime_state()
        return self.snapshot()

    def scheduled_preopen_rotation(self) -> bool:
        self.initialize()
        return self._refresh_or_regenerate(reason="scheduled-preopen-rotation", force=True)

    def ensure_token_fresh(self, force_profile: bool = False) -> bool:
        self.initialize()
        snapshot = self.snapshot()
        if not snapshot.client_id:
            raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan client id is not configured")
        if not snapshot.access_token:
            return self._regenerate_access_token(reason="missing-access-token")

        now = datetime.now(timezone.utc)
        needs_profile = force_profile or not snapshot.last_profile_checked_at
        if snapshot.last_profile_checked_at:
            needs_profile = needs_profile or (now - snapshot.last_profile_checked_at).total_seconds() >= max(settings.dhan_profile_check_seconds, 60)

        needs_renewal = False
        if snapshot.expires_at:
            needs_renewal = (snapshot.expires_at - now).total_seconds() <= max(settings.dhan_token_renewal_lead_seconds, 60)

        if needs_profile:
            try:
                profile = self._fetch_profile(snapshot.client_id, snapshot.access_token)
            except DhanApiError as exc:
                if exc.auth_failed or needs_renewal:
                    return self._refresh_or_regenerate(reason="profile-check-failed")
                raise
            self._record_profile(profile)
            snapshot = self.snapshot()
            if snapshot.expires_at:
                needs_renewal = (snapshot.expires_at - now).total_seconds() <= max(settings.dhan_token_renewal_lead_seconds, 60)
            if snapshot.data_plan_status and snapshot.data_plan_status.lower() != "active":
                raise DhanApiError(
                    "DATA_PLAN_INACTIVE",
                    f"Dhan data plan is {snapshot.data_plan_status}",
                )
            if snapshot.data_valid_until and snapshot.data_valid_until < now:
                raise DhanApiError(
                    "DATA_PLAN_INACTIVE",
                    "Dhan market-data entitlement has expired",
                )

        if needs_renewal:
            return self._refresh_or_regenerate(reason="scheduled-renewal")
        return False

    def renew_access_token(self, reason: str) -> bool:
        self.initialize()
        return self._refresh_or_regenerate(reason=reason)

    def call(self, operation_name: str, fn: Callable[[Dhanhq], T], *, allow_auth_retry: bool = True) -> T:
        self.ensure_token_fresh()

        attempt = 0
        while True:
            attempt += 1
            client = self.create_client()
            try:
                result = fn(client)
            except Exception as exc:  # noqa: BLE001
                raise DhanApiError(
                    "DHAN_TRANSPORT_FAILED",
                    f"{operation_name} request failed: {type(exc).__name__}: {exc}",
                ) from exc

            try:
                data = self._unwrap_sdk_result(operation_name, result)
            except DhanApiError as exc:
                if exc.auth_failed and allow_auth_retry and attempt == 1:
                    self._refresh_or_regenerate(reason=f"{operation_name}-auth-retry")
                    continue
                raise

            with self._lock:
                self._last_rest_success_at = datetime.now(timezone.utc)
            return data

    def _load_from_storage(self) -> None:
        env_client_id = (settings.dhan_client_id or "").strip() or None
        env_access_token = (settings.dhan_access_token or "").strip() or None
        env_expires_at = _decode_token_expiry(env_access_token)

        record = None
        db = SessionLocal()
        try:
            record = db.query(ServiceCredential).filter(ServiceCredential.provider == "dhan").first()
        finally:
            db.close()

        # Priority: pick whichever source has the latest expiry
        candidates = []
        if env_access_token and env_expires_at:
            candidates.append(("env", env_client_id, env_access_token, env_expires_at, None, None))
        if record and record.access_token:
            record_expires_at = _ensure_utc(record.expires_at) or _decode_token_expiry(record.access_token)
            if record_expires_at:
                candidates.append(
                    (
                        record.token_source or "db",
                        record.client_id,
                        record.access_token,
                        record_expires_at,
                        _ensure_utc(record.last_refreshed_at),
                        _ensure_utc(record.last_validated_at),
                    )
                )

        if candidates:
            candidates.sort(key=lambda c: c[3] if c[3] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            chosen_source, chosen_client_id, chosen_token, chosen_expires_at, chosen_last_refreshed_at, chosen_last_validated_at = candidates[0]
        else:
            chosen_source = None
            chosen_client_id = env_client_id
            chosen_token = None
            chosen_expires_at = None
            chosen_last_refreshed_at = None
            chosen_last_validated_at = None

        with self._lock:
            token_changed = chosen_token != self._access_token
            had_runtime_token = self._access_token is not None
            self._client_id = chosen_client_id
            self._access_token = chosen_token
            self._expires_at = chosen_expires_at
            self._token_source = chosen_source
            self._last_refreshed_at = chosen_last_refreshed_at
            self._last_profile_checked_at = chosen_last_validated_at
            self._last_lease_issued_at = _ensure_utc(record.last_lease_issued_at) if record else None
            self._data_plan_status = record.data_plan_status if record else None
            self._data_valid_until = _ensure_utc(record.data_valid_until) if record else None
            self._generation = int(record.generation or 0) if record else 0
            if token_changed and had_runtime_token:
                self._generation = max(self._generation, 0) + 1

        if chosen_client_id and chosen_token:
            self._persist_runtime_state()

    def _persist_runtime_state(self) -> None:
        snapshot = self.snapshot()
        if not snapshot.client_id or not snapshot.access_token:
            return
        db = SessionLocal()
        try:
            record = db.query(ServiceCredential).filter(ServiceCredential.provider == "dhan").first()
            if not record:
                record = ServiceCredential(provider="dhan", client_id=snapshot.client_id, access_token=snapshot.access_token)
            record.client_id = snapshot.client_id
            record.access_token = snapshot.access_token
            record.expires_at = snapshot.expires_at
            record.token_source = snapshot.token_source or "authority"
            record.generation = snapshot.generation
            record.last_refreshed_at = snapshot.last_refreshed_at
            record.last_validated_at = snapshot.last_profile_checked_at
            record.data_plan_status = snapshot.data_plan_status
            record.data_valid_until = snapshot.data_valid_until
            record.last_lease_issued_at = snapshot.last_lease_issued_at
            db.add(record)
            db.commit()
        finally:
            db.close()

    def _apply_new_token(
        self,
        *,
        client_id: str,
        access_token: str,
        expires_at: datetime | None,
        token_source: str,
        refreshed_at: datetime | None,
    ) -> None:
        with self._lock:
            token_changed = access_token != self._access_token
            self._client_id = client_id
            self._access_token = access_token
            self._expires_at = expires_at
            self._token_source = token_source
            self._last_refreshed_at = refreshed_at
            if token_changed:
                self._generation += 1

        self._persist_runtime_state()

    def _record_profile(self, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        expires_at = _parse_ist_datetime(str(payload.get("tokenValidity") or ""))
        data_valid_until = _parse_ist_datetime(str(payload.get("dataValidity") or ""))
        with self._lock:
            self._last_profile_checked_at = now
            self._data_plan_status = str(payload.get("dataPlan") or "").strip() or None
            self._data_valid_until = data_valid_until
            if expires_at:
                self._expires_at = expires_at

        self._persist_runtime_state()

    def _refresh_or_regenerate(self, *, reason: str, force: bool = False) -> bool:
        gen_before = self.snapshot().generation
        with self._renewal_lock:
            if self.snapshot().generation != gen_before:
                return True
            snapshot = self.snapshot()
            now = datetime.now(timezone.utc)
            force_rotation = force or any(marker in reason.lower() for marker in ("auth", "profile", "missing"))
            if not force_rotation and snapshot.access_token and snapshot.expires_at:
                remaining = (snapshot.expires_at - now).total_seconds()
                if remaining > max(settings.dhan_token_renewal_lead_seconds, 60):
                    logger.info("Token has %.0fh remaining, treating auth error as transient (%s)", remaining / 3600, reason)
                    return False

            if snapshot.client_id and snapshot.access_token:
                can_renew = snapshot.token_source not in ("totp",)
                if can_renew:
                    try:
                        return self._renew_access_token(reason=reason)
                    except DhanApiError as exc:
                        logger.warning("Dhan token renewal failed (%s)", exc.reason)

            if settings.dhan_pin and settings.dhan_totp_secret:
                try:
                    return self._regenerate_access_token(reason=f"{reason}-totp-fallback")
                except DhanApiError as exc:
                    logger.error("TOTP regeneration also failed: %s", exc.message)

            return False

    def _renew_access_token(self, *, reason: str) -> bool:
        snapshot = self.snapshot()
        if not snapshot.client_id or not snapshot.access_token:
            raise DhanApiError("DHAN_TOKEN_RENEWAL_FAILED", "Cannot renew Dhan token without an active access token", auth_failed=True)

        payload = self._request_json(
            "POST",
            f"{DHAN_API_BASE}/RenewToken",
            headers=self._headers(snapshot.client_id, snapshot.access_token),
            failure_reason="DHAN_TOKEN_RENEWAL_FAILED",
            auth_failed=True,
        )
        next_token = str(payload.get("accessToken") or payload.get("token") or "").strip()
        if not next_token:
            raise DhanApiError("DHAN_TOKEN_RENEWAL_FAILED", f"Dhan renew token response did not include a token: {_extract_error_text(payload)}", auth_failed=True, payload=payload)
        expires_at = _parse_ist_datetime(str(payload.get("expiryTime") or "")) or _decode_token_expiry(next_token)
        refreshed_at = _parse_ist_datetime(str(payload.get("createTime") or "")) or datetime.now(timezone.utc)
        profile = self._fetch_profile(snapshot.client_id, next_token)
        logger.info("Renewed Dhan access token for %s via %s", snapshot.client_id, reason)
        self._apply_new_token(
            client_id=snapshot.client_id,
            access_token=next_token,
            expires_at=expires_at,
            token_source="renew",
            refreshed_at=refreshed_at,
        )
        self._record_profile(profile)
        return True

    def _regenerate_access_token(self, *, reason: str) -> bool:
        client_id = (self.snapshot().client_id or settings.dhan_client_id or "").strip()
        pin = (settings.dhan_pin or "").strip()
        totp_secret = (settings.dhan_totp_secret or "").strip()
        if not client_id or not pin or not totp_secret:
            raise DhanApiError(
                "DHAN_TOKEN_RENEWAL_FAILED",
                "Dhan token renewal failed and TOTP fallback is not configured",
                auth_failed=True,
            )

        # Dhan rate-limits generateAccessToken to once every 2 minutes.
        # Track attempt time (not just success) so we don't spam the endpoint.
        elapsed = time.time() - self._last_totp_generation_at
        if elapsed < 130:  # 2m10s to be safe
            snapshot = self.snapshot()
            if snapshot.access_token and snapshot.expires_at and snapshot.expires_at > datetime.now(timezone.utc):
                logger.info("Skipping TOTP regeneration (%.0fs cooldown, current token still valid)", 130 - elapsed)
                return False
            # Token is expired and we're rate-limited — wait out the cooldown.
            wait = 130 - elapsed
            logger.warning("TOTP rate-limited but token expired; waiting %.0fs for cooldown", wait)
            time.sleep(wait)

        # Record attempt time BEFORE calling Dhan, so concurrent threads
        # that enter after the lock is released see the cooldown immediately.
        self._last_totp_generation_at = time.time()

        next_token: str = ""
        payload = None
        last_error: DhanApiError | None = None
        for totp in _totp_candidates(totp_secret):
            try:
                candidate_payload = self._request_json(
                    "POST",
                    f"{DHAN_AUTH_BASE}/generateAccessToken",
                    params={"dhanClientId": client_id, "pin": pin, "totp": totp},
                    failure_reason="DHAN_TOKEN_REGENERATION_FAILED",
                    auth_failed=True,
                )
            except DhanApiError as exc:
                last_error = exc
                continue
            # Dhan may return HTTP 200 with {"status": "error"} for invalid TOTP;
            # only accept the response if it actually contains an access token.
            token = str(candidate_payload.get("accessToken") or candidate_payload.get("token") or "").strip()
            if token:
                next_token = token
                payload = candidate_payload
                break
            last_error = DhanApiError(
                "DHAN_TOKEN_REGENERATION_FAILED",
                f"Dhan TOTP response missing access token: {_extract_error_text(candidate_payload)}",
                auth_failed=True,
                payload=candidate_payload,
            )

        if not next_token:
            if last_error:
                raise last_error
            raise DhanApiError(
                "DHAN_TOKEN_REGENERATION_FAILED",
                "Dhan TOTP regeneration failed without a response payload",
                auth_failed=True,
            )
        self._last_totp_generation_at = time.time()
        expires_at = _parse_ist_datetime(str(payload.get("expiryTime") or "")) or _decode_token_expiry(next_token)
        refreshed_at = datetime.now(timezone.utc)
        profile = self._fetch_profile(client_id, next_token)
        logger.info("Regenerated Dhan access token for %s via %s", client_id, reason)
        self._apply_new_token(
            client_id=client_id,
            access_token=next_token,
            expires_at=expires_at,
            token_source="totp",
            refreshed_at=refreshed_at,
        )
        self._record_profile(profile)
        return True

    def _fetch_profile(self, client_id: str, access_token: str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"{DHAN_API_BASE}/profile",
            headers=self._headers(client_id, access_token),
            failure_reason="DHAN_PROFILE_FAILED",
            auth_failed=True,
        )

    @staticmethod
    def _headers(client_id: str, access_token: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "access-token": access_token,
            "client-id": client_id,
            "dhanClientId": client_id,
        }

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        failure_reason: str,
        auth_failed: bool,
    ) -> dict[str, Any]:
        try:
            response = httpx.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=settings.dhan_http_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise DhanApiError(
                "DHAN_TRANSPORT_FAILED",
                f"Dhan request to {url} failed: {type(exc).__name__}: {exc}",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise DhanApiError(
                failure_reason,
                f"Dhan request to {url} returned invalid JSON: {response.text[:300]}",
                auth_failed=auth_failed and response.status_code in {401, 403},
            ) from exc

        if response.status_code >= 400:
            message = _extract_error_text(payload) or f"HTTP {response.status_code}"
            is_auth_failure = response.status_code in {401, 403} or self._looks_like_auth_error(payload)
            lowered = message.lower()
            if is_auth_failure:
                reason = failure_reason
            elif any(marker in lowered for marker in RATE_LIMIT_MARKERS) or response.status_code == 429:
                reason = "DHAN_RATE_LIMITED"
            elif any(marker in lowered for marker in STATIC_IP_MARKERS):
                reason = "DHAN_STATIC_IP_REJECTED"
            else:
                reason = failure_reason
            raise DhanApiError(
                reason,
                f"{url} failed: {message}",
                auth_failed=auth_failed and is_auth_failure,
                payload=payload,
            )
        return payload if isinstance(payload, dict) else {}

    def _unwrap_sdk_result(self, operation_name: str, result: Any) -> T:
        if not isinstance(result, dict):
            raise DhanApiError(
                "DHAN_PROTOCOL_FAILED",
                f"{operation_name} returned {type(result).__name__}, expected dict",
                payload=result,
            )

        status = str(result.get("status") or "").lower()
        if status == "success":
            return result.get("data")

        payload = result.get("data")
        message = _extract_error_text(payload) or _extract_error_text(result.get("remarks")) or f"{operation_name} failed"
        auth_failed = self._looks_like_auth_error(payload) or self._looks_like_auth_error(result.get("remarks"))
        lowered = message.lower()
        if auth_failed:
            reason = "DHAN_AUTH_FAILED"
        elif any(marker in lowered for marker in RATE_LIMIT_MARKERS):
            reason = "DHAN_RATE_LIMITED"
        elif any(marker in lowered for marker in STATIC_IP_MARKERS):
            reason = "DHAN_STATIC_IP_REJECTED"
        else:
            reason = "DHAN_UPSTREAM_FAILED"
        raise DhanApiError(
            reason,
            f"{operation_name} failed: {message}",
            auth_failed=auth_failed,
            payload=result,
        )

    def _looks_like_auth_error(self, payload: Any) -> bool:
        text = _extract_error_text(payload).lower()
        return any(marker in text for marker in AUTH_ERROR_MARKERS)

    @staticmethod
    def _next_preopen_rotation_after(now: datetime | None = None) -> datetime:
        current = (now or datetime.now(timezone.utc)).astimezone(IST)
        target_date = current.date()
        target_time = dt_time(hour=8, minute=50)
        while True:
            if target_date.weekday() < 5 and not holiday_name(target_date):
                candidate = datetime.combine(target_date, target_time, tzinfo=IST)
                if candidate > current:
                    return candidate.astimezone(timezone.utc)
            target_date = target_date + timedelta(days=1)

    async def _scheduler_loop(self) -> None:
        while True:
            stop_event = self._scheduler_stop
            if stop_event is None:
                return
            next_run = self._next_preopen_rotation_after()
            wait_seconds = max((next_run - datetime.now(timezone.utc)).total_seconds(), 1)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=wait_seconds)
                return
            except asyncio.TimeoutError:
                pass
            try:
                rotated = await asyncio.to_thread(self.scheduled_preopen_rotation)
                logger.info("Scheduled Dhan pre-open rotation completed (rotated=%s)", rotated)
            except Exception:  # noqa: BLE001
                logger.exception("Scheduled Dhan pre-open rotation failed")


dhan_credential_service = DhanCredentialService()
