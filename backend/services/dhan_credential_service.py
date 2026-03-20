from __future__ import annotations
import asyncio, base64, hashlib, hmac, json, logging, struct, threading, time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, TypeVar
import httpx
from dhanhq import dhanhq as Dhanhq
from config import get_settings
from database import SessionLocal
from market_hours import IST
from models import ServiceCredential

settings, logger, T = get_settings(), logging.getLogger("lite.dhan.credentials"), TypeVar("T")
DHAN_API_BASE, DHAN_AUTH_BASE = "https://api.dhan.co/v2", "https://auth.dhan.co/app"
AUTH_ERROR_MARKERS = ("authentication failed", "token invalid", "invalid token", "invalid jwt", "unauthorized", "401")
RATE_LIMIT_MARKERS, STATIC_IP_MARKERS = ("too many request", "too many requests", "429", "805"), ("static ip", "whitelisted ip", "ip mismatch")

class DhanApiError(RuntimeError):
    def __init__(self, reason: str, message: str, *, auth_failed: bool = False, payload: Any | None = None) -> None:
        super().__init__(message); self.reason, self.message, self.auth_failed, self.payload = reason, message, auth_failed, payload

@dataclass(frozen=True, slots=True)
class DhanCredentialSnapshot:
    configured: bool; client_id: str | None; access_token: str | None; expires_at: datetime | None
    token_source: str | None; last_refreshed_at: datetime | None; last_profile_checked_at: datetime | None
    last_rest_success_at: datetime | None; data_plan_status: str | None; data_valid_until: datetime | None
    last_lease_issued_at: datetime | None; generation: int; totp_regeneration_enabled: bool

def _decode_token_expiry(raw: str | None) -> datetime | None:
    if not raw or raw.count(".") < 2: return None
    try: p = raw.split(".", 2)[1]; p += "=" * (-len(p) % 4); exp = json.loads(base64.urlsafe_b64decode(p)).get("exp")
    except Exception: return None
    return datetime.fromtimestamp(exp, timezone.utc) if isinstance(exp, (int, float)) else None

def _parse_ist_datetime(value: str | None) -> datetime | None:
    if not value or not (c := value.strip()): return None
    for f in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(c, f).replace(tzinfo=IST).astimezone(timezone.utc)
        except ValueError: continue
    try: parsed = datetime.fromisoformat(c.replace("Z", "+00:00"))
    except ValueError: return None
    return (parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed).astimezone(timezone.utc)

def _ensure_utc(v: datetime | None) -> datetime | None:
    return None if v is None else (v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc))

def _totp_code(secret: str, *, for_time: float | None = None) -> str:
    key, counter = base64.b32decode(secret.replace(" ", "").upper(), casefold=True), int((time.time() if for_time is None else for_time) // 30)
    d = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest(); o = d[-1] & 0x0F
    return f"{(struct.unpack('>I', d[o:o+4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"

def _totp_candidates(secret: str) -> list[str]:
    now, seen = time.time(), []
    for off in (0, -30, 30):
        c = _totp_code(secret, for_time=now + off)
        if c not in seen: seen.append(c)
    return seen

def _classify(msg: str, status: int = 0) -> tuple[str, bool]:
    low = msg.lower(); is_auth = status in {401, 403} or any(m in low for m in AUTH_ERROR_MARKERS)
    r = "DHAN_RATE_LIMITED" if (any(m in low for m in RATE_LIMIT_MARKERS) or status == 429) else "DHAN_STATIC_IP_REJECTED" if any(m in low for m in STATIC_IP_MARKERS) else None
    return (r or ("DHAN_AUTH_FAILED" if is_auth else ""), is_auth)

class DhanCredentialService:
    def __init__(self) -> None:
        self._lock, self._renewal_lock = threading.RLock(), threading.Lock()
        self._initialized = False; self._scheduler_task: asyncio.Task | None = None; self._scheduler_stop: asyncio.Event | None = None
        self._client_id: str | None = None; self._access_token: str | None = None; self._expires_at: datetime | None = None
        self._token_source: str | None = None; self._last_refreshed_at: datetime | None = None
        self._last_profile_checked_at: datetime | None = None; self._last_lease_issued_at: datetime | None = None
        self._last_rest_success_at: datetime | None = None; self._data_plan_status: str | None = None
        self._data_valid_until: datetime | None = None; self._generation = 0; self._last_totp_generation_at: float = 0.0

    def initialize(self, *, force_reload: bool = False) -> None:
        with self._lock:
            if self._initialized and not force_reload: return
            self._initialized = True
        self._load_from_storage()

    def reset_runtime_state(self) -> None:
        with self._lock:
            self._initialized = False; self._generation = 0
            self._client_id = self._access_token = self._expires_at = self._token_source = None
            self._last_refreshed_at = self._last_profile_checked_at = self._last_lease_issued_at = None
            self._last_rest_success_at = self._data_plan_status = self._data_valid_until = None

    def snapshot(self) -> DhanCredentialSnapshot:
        self.initialize()
        with self._lock:
            return DhanCredentialSnapshot(configured=bool(self._client_id and self._access_token), client_id=self._client_id,
                access_token=self._access_token, expires_at=self._expires_at, token_source=self._token_source,
                last_refreshed_at=self._last_refreshed_at, last_profile_checked_at=self._last_profile_checked_at,
                last_rest_success_at=self._last_rest_success_at, data_plan_status=self._data_plan_status,
                data_valid_until=self._data_valid_until, last_lease_issued_at=self._last_lease_issued_at,
                generation=self._generation, totp_regeneration_enabled=bool(settings.dhan_pin and settings.dhan_totp_secret))

    def configured(self) -> bool: return self.snapshot().configured

    def create_client(self) -> Dhanhq:
        s = self.snapshot()
        if not s.client_id or not s.access_token: raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan credentials are not configured")
        return Dhanhq(s.client_id, s.access_token)

    def ensure_token_fresh(self, force_profile: bool = False) -> bool:
        self.initialize(); snap = self.snapshot(); now = datetime.now(timezone.utc)
        if not snap.client_id: raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan client id is not configured")
        if not snap.access_token: return self._regenerate_via_totp(reason="missing-access-token")
        needs_profile = force_profile or not snap.last_profile_checked_at or (now - snap.last_profile_checked_at).total_seconds() >= max(settings.dhan_profile_check_seconds, 60)
        needs_renewal = bool(snap.expires_at and (snap.expires_at - now).total_seconds() <= max(settings.dhan_token_renewal_lead_seconds, 60))
        if needs_profile:
            try: profile = self._fetch_profile(snap.client_id, snap.access_token)
            except DhanApiError as exc:
                if exc.auth_failed or needs_renewal: return self._regenerate_via_totp(reason="profile-check-failed")
                raise
            self._record_profile(profile); snap = self.snapshot()
            if snap.expires_at: needs_renewal = (snap.expires_at - now).total_seconds() <= max(settings.dhan_token_renewal_lead_seconds, 60)
            if snap.data_plan_status and snap.data_plan_status.lower() != "active": raise DhanApiError("DATA_PLAN_INACTIVE", f"Dhan data plan is {snap.data_plan_status}")
            if snap.data_valid_until and snap.data_valid_until < now: raise DhanApiError("DATA_PLAN_INACTIVE", "Dhan market-data entitlement has expired")
        return self._regenerate_via_totp(reason="scheduled-renewal") if needs_renewal else False

    def call(self, operation_name: str, fn: Callable[[Dhanhq], T], *, allow_auth_retry: bool = True) -> T:
        self.ensure_token_fresh()
        for attempt in (1, 2):
            try: result = fn(self.create_client())
            except Exception as exc: raise DhanApiError("DHAN_TRANSPORT_FAILED", f"{operation_name} request failed: {type(exc).__name__}: {exc}") from exc
            try: data = self._unwrap_sdk_result(operation_name, result)
            except DhanApiError as exc:
                if exc.auth_failed and allow_auth_retry and attempt == 1: self._regenerate_via_totp(reason=f"{operation_name}-auth-retry"); continue
                raise
            with self._lock: self._last_rest_success_at = datetime.now(timezone.utc)
            return data

    def issue_lease(self) -> DhanCredentialSnapshot:
        self.ensure_token_fresh(); snap = self.snapshot()
        if not snap.client_id or not snap.access_token: raise DhanApiError("DHAN_NOT_CONFIGURED", "Dhan credentials are not configured")
        if snap.data_plan_status and snap.data_plan_status.lower() != "active": raise DhanApiError("DATA_PLAN_INACTIVE", f"Dhan data plan is {snap.data_plan_status}")
        with self._lock: self._last_lease_issued_at = datetime.now(timezone.utc)
        self._persist_runtime_state(); return self.snapshot()

    def scheduled_preopen_rotation(self) -> bool:
        self.initialize(); return self._regenerate_via_totp(reason="scheduled-rotation", force=True)

    async def start_background_tasks(self) -> None:
        if self._scheduler_task: return
        self._scheduler_stop = asyncio.Event(); self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop_background_tasks(self) -> None:
        if not self._scheduler_task: return
        if self._scheduler_stop: self._scheduler_stop.set()
        self._scheduler_task.cancel()
        try: await self._scheduler_task
        except asyncio.CancelledError: pass
        self._scheduler_task = self._scheduler_stop = None

    def _load_from_storage(self) -> None:
        env_cid, env_tok = (settings.dhan_client_id or "").strip() or None, (settings.dhan_access_token or "").strip() or None
        db = SessionLocal()
        try: rec = db.query(ServiceCredential).filter(ServiceCredential.provider == "dhan").first()
        finally: db.close()
        if rec and rec.access_token:
            cid, tok, src = rec.client_id, rec.access_token, rec.token_source or "db"
            exp, ref, val = _ensure_utc(rec.expires_at) or _decode_token_expiry(tok), _ensure_utc(rec.last_refreshed_at), _ensure_utc(rec.last_validated_at)
        elif env_tok: cid, tok, src, exp, ref, val = env_cid, env_tok, "env", _decode_token_expiry(env_tok), None, None
        else: cid, tok, src, exp, ref, val = env_cid, None, None, None, None, None
        with self._lock:
            self._client_id, self._access_token, self._expires_at = cid, tok, exp
            self._token_source, self._last_refreshed_at, self._last_profile_checked_at = src, ref, val
            self._last_lease_issued_at = _ensure_utc(rec.last_lease_issued_at) if rec else None
            self._data_plan_status, self._data_valid_until = (rec.data_plan_status if rec else None), (_ensure_utc(rec.data_valid_until) if rec else None)
            self._generation = int(rec.generation or 0) if rec else 0
        if cid and tok: self._persist_runtime_state()

    def _persist_runtime_state(self) -> None:
        s = self.snapshot()
        if not s.client_id or not s.access_token: return
        db = SessionLocal()
        try:
            r = db.query(ServiceCredential).filter(ServiceCredential.provider == "dhan").first()
            if not r: r = ServiceCredential(provider="dhan", client_id=s.client_id, access_token=s.access_token)
            r.client_id, r.access_token, r.expires_at = s.client_id, s.access_token, s.expires_at
            r.token_source, r.generation = s.token_source or "authority", s.generation
            r.last_refreshed_at, r.last_validated_at = s.last_refreshed_at, s.last_profile_checked_at
            r.data_plan_status, r.data_valid_until, r.last_lease_issued_at = s.data_plan_status, s.data_valid_until, s.last_lease_issued_at
            db.add(r); db.commit()
        finally: db.close()

    def _apply_new_token(self, *, client_id: str, access_token: str, expires_at: datetime | None, token_source: str, refreshed_at: datetime | None) -> None:
        with self._lock:
            changed = access_token != self._access_token
            self._client_id, self._access_token = client_id, access_token
            self._expires_at, self._token_source, self._last_refreshed_at = expires_at, token_source, refreshed_at
            if changed: self._generation += 1
        self._persist_runtime_state()

    def _record_profile(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._last_profile_checked_at = datetime.now(timezone.utc)
            self._data_plan_status = str(payload.get("dataPlan") or "").strip() or None
            self._data_valid_until = _parse_ist_datetime(str(payload.get("dataValidity") or ""))
            exp = _parse_ist_datetime(str(payload.get("tokenValidity") or ""))
            if exp: self._expires_at = exp
        self._persist_runtime_state()

    def _fetch_profile(self, client_id: str, access_token: str) -> dict[str, Any]:
        return self._request_json("GET", f"{DHAN_API_BASE}/profile", headers={"Accept": "application/json", "Content-Type": "application/json", "access-token": access_token, "client-id": client_id, "dhanClientId": client_id})

    def _regenerate_via_totp(self, *, reason: str, force: bool = False) -> bool:
        cid, pin, secret = (self.snapshot().client_id or settings.dhan_client_id or "").strip(), (settings.dhan_pin or "").strip(), (settings.dhan_totp_secret or "").strip()
        if not cid or not pin or not secret: raise DhanApiError("DHAN_TOKEN_RENEWAL_FAILED", "TOTP regeneration not configured", auth_failed=True)
        gen_before = self.snapshot().generation
        with self._renewal_lock:
            if not force and self.snapshot().generation != gen_before: return True
            elapsed = time.time() - self._last_totp_generation_at
            if elapsed < 130:
                s = self.snapshot()
                if s.access_token and s.expires_at and s.expires_at > datetime.now(timezone.utc):
                    logger.info("Skipping TOTP regen (%.0fs cooldown, token valid)", 130 - elapsed); return False
                logger.warning("TOTP rate-limited, token expired; waiting %.0fs", 130 - elapsed); time.sleep(130 - elapsed)
            self._last_totp_generation_at = time.time()
            next_tok, pay, last_err = "", None, None
            for totp in _totp_candidates(secret):
                try: resp = self._request_json("POST", f"{DHAN_AUTH_BASE}/generateAccessToken", params={"dhanClientId": cid, "pin": pin, "totp": totp})
                except DhanApiError as e: last_err = e; continue
                t = str(resp.get("accessToken") or resp.get("token") or "").strip()
                if t: next_tok, pay = t, resp; break
                last_err = DhanApiError("DHAN_TOKEN_REGENERATION_FAILED", f"TOTP response missing token: {str(resp)[:500]}", auth_failed=True, payload=resp)
            if not next_tok: raise last_err or DhanApiError("DHAN_TOKEN_REGENERATION_FAILED", "TOTP regeneration failed", auth_failed=True)
            self._last_totp_generation_at = time.time()
            exp = _parse_ist_datetime(str(pay.get("expiryTime") or "")) or _decode_token_expiry(next_tok)
            profile = self._fetch_profile(cid, next_tok); logger.info("Regenerated Dhan token for %s via %s", cid, reason)
            self._apply_new_token(client_id=cid, access_token=next_tok, expires_at=exp, token_source="totp", refreshed_at=datetime.now(timezone.utc))
            self._record_profile(profile); return True

    def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("timeout", settings.dhan_http_timeout_seconds)
        try: response = httpx.request(method, url, **kwargs)
        except Exception as exc: raise DhanApiError("DHAN_TRANSPORT_FAILED", f"Dhan request to {url} failed: {type(exc).__name__}: {exc}") from exc
        try: payload = response.json()
        except ValueError as exc: raise DhanApiError("DHAN_REQUEST_FAILED", f"Dhan {url} invalid JSON: {response.text[:300]}", auth_failed=response.status_code in {401, 403}) from exc
        if response.status_code >= 400:
            msg = str(payload)[:500]; reason, is_auth = _classify(msg, response.status_code)
            raise DhanApiError(reason or "DHAN_REQUEST_FAILED", f"{url} failed: {msg}", auth_failed=is_auth, payload=payload)
        return payload if isinstance(payload, dict) else {}

    def _unwrap_sdk_result(self, op: str, result: Any) -> Any:
        if not isinstance(result, dict): raise DhanApiError("DHAN_PROTOCOL_FAILED", f"{op} returned {type(result).__name__}, expected dict", payload=result)
        if str(result.get("status") or "").lower() == "success": return result.get("data")
        msg = str(result.get("data"))[:500] or str(result.get("remarks"))[:500] or f"{op} failed"
        reason, auth = _classify(msg); auth = auth or any(m in str(result.get("remarks")).lower() for m in AUTH_ERROR_MARKERS)
        raise DhanApiError(reason or "DHAN_UPSTREAM_FAILED", f"{op} failed: {msg}", auth_failed=auth, payload=result)

    @staticmethod
    def _next_rotation_time(now: datetime | None = None) -> datetime:
        cur = now or datetime.now(timezone.utc); t = cur.replace(hour=3, minute=20, second=0, microsecond=0)
        return t if cur < t else t + timedelta(days=1)

    async def _scheduler_loop(self) -> None:
        while True:
            stop = self._scheduler_stop
            if stop is None: return
            try: await asyncio.wait_for(stop.wait(), timeout=max((self._next_rotation_time() - datetime.now(timezone.utc)).total_seconds(), 1)); return
            except asyncio.TimeoutError: pass
            try: rotated = await asyncio.to_thread(self.scheduled_preopen_rotation); logger.info("Scheduled rotation completed (rotated=%s)", rotated)
            except Exception: logger.exception("Scheduled rotation failed")

dhan_credential_service = DhanCredentialService()
