from __future__ import annotations

import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.gettempdir()) / f"lite-dhan-credential-tests-{uuid.uuid4().hex}"
SIGNAL_ROOT = TEST_ROOT / "signals"
SIGNAL_ROOT.mkdir(parents=True, exist_ok=True)
(SIGNAL_ROOT / "logs").mkdir(parents=True, exist_ok=True)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("LITE_DATABASE_URL", f"sqlite:///{TEST_ROOT / 'lite-test.db'}")
os.environ.setdefault("SIGNAL_ROOT", str(SIGNAL_ROOT))
os.environ.setdefault("ALLOW_PUBLIC_SIGNUP", "true")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@lite.trade")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "lite-admin-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_NAME", "Lite Admin")
os.environ.setdefault("BOOTSTRAP_AGENT_KEY", "lite-agent-dev-key")
os.environ.setdefault("BOOTSTRAP_AGENT_NAME", "bootstrap-agent")

from database import Base, engine
import services.dhan_credential_service as dhan_credentials_module
from services.dhan_credential_service import (
    DhanApiError,
    DhanCredentialService,
    DhanRateLimiter,
    _classify_dhan_error,
)


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.mark.parametrize(
    ("code", "message", "status", "expected_reason", "expected_auth"),
    [
        ("807", "Access token is expired", 401, "DHAN_AUTH_FAILED", True),
        ("808", "Authentication Failed - Client ID or Access Token invalid", 401, "DHAN_AUTH_FAILED", True),
        ("DH-906", "Any broker wording can change", 400, "DHAN_AUTH_FAILED", True),
        ("806", "Data APIs not subscribed", 403, "DHAN_ACCESS_DENIED", False),
        ("DH-903", "Static IP mismatch for this request", 400, "DHAN_STATIC_IP_REJECTED", False),
        ("805", "Too many requests or connections", 429, "DHAN_RATE_LIMITED", False),
        ("811", "Invalid Expiry Date", 400, "DHAN_INVALID_REQUEST", False),
        ("DH-907", "No data present for requested range", 404, "DHAN_NO_DATA", False),
        ("DH-907", "Incorrect parameters supplied", 400, "DHAN_INVALID_REQUEST", False),
        ("DH-908", "Server was not able to process API request", 500, "DHAN_UPSTREAM_FAILED", False),
    ],
)
def test_classify_dhan_error_uses_documented_code_families(
    code: str,
    message: str,
    status: int,
    expected_reason: str,
    expected_auth: bool,
) -> None:
    assert _classify_dhan_error(code, message, status=status) == (expected_reason, expected_auth)


def test_request_json_uses_structured_error_fields() -> None:
    service = DhanCredentialService()

    class Response:
        status_code = 400
        text = '{"errorCode":"811","errorMessage":"Invalid Expiry Date"}'

        @staticmethod
        def json() -> dict[str, str]:
            return {"errorCode": "811", "errorMessage": "Invalid Expiry Date"}

    def fake_request(*args, **kwargs):
        return Response()

    import services.dhan_credential_service as module

    original_request = module.httpx.request
    module.httpx.request = fake_request
    try:
        with pytest.raises(DhanApiError) as exc_info:
            service._request_json("GET", "https://api.dhan.co/v2/example")
    finally:
        module.httpx.request = original_request

    assert exc_info.value.reason == "DHAN_INVALID_REQUEST"


def test_classify_dhan_error_does_not_mark_rate_limit_as_auth_failure() -> None:
    assert _classify_dhan_error("DH-904", "Too many requests", status=401) == ("DHAN_RATE_LIMITED", False)


def test_unwrap_sdk_result_surfaces_no_data_reason() -> None:
    service = DhanCredentialService()
    payload = {
        "status": "failure",
        "remarks": {"error_code": "DH-907", "error_message": "No data present"},
        "data": {},
    }

    with pytest.raises(DhanApiError) as exc_info:
        service._unwrap_sdk_result("historical_daily_data", payload)

    assert exc_info.value.reason == "DHAN_NO_DATA"


def test_rate_limiter_keeps_reserved_capacity_for_critical_calls() -> None:
    limiter = DhanRateLimiter(rate_per_second=0.0, capacity=2, burst_cap=2, reserved_capacity=1)

    assert limiter.acquire(timeout=0.01, operation="low-1", priority="normal") is True
    assert limiter.acquire(timeout=0.01, operation="low-2", priority="normal") is False
    assert limiter.acquire(timeout=0.01, operation="high-1", priority="high") is True
    limiter = DhanRateLimiter(rate_per_second=0.0, capacity=2, burst_cap=2, reserved_capacity=1)
    assert limiter.acquire(timeout=0.01, operation="low-1", priority="normal") is True
    assert limiter.acquire(timeout=0.01, operation="critical-1", priority="critical") is True


def test_critical_budget_bypasses_local_backoff() -> None:
    service = DhanCredentialService()
    service._global_backoff_until = 10**12

    with pytest.raises(DhanApiError) as non_critical_exc:
        service._acquire_budget("historical_daily_data")
    assert non_critical_exc.value.reason == "DHAN_RATE_LIMITED"

    service._acquire_budget("profile")


def test_call_runs_token_refresh_before_normal_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    service = DhanCredentialService()
    limiter = DhanRateLimiter(rate_per_second=0.0, capacity=3, burst_cap=3, reserved_capacity=3)
    ensure_calls: list[str] = []

    monkeypatch.setattr(dhan_credentials_module, "_api_rate_limiter", limiter)
    monkeypatch.setattr(service, "ensure_token_fresh", lambda *args, **kwargs: ensure_calls.append("called") or False)

    with pytest.raises(DhanApiError) as exc_info:
        service.call("historical_daily_data", lambda client: {"status": "success", "data": {"ok": True}})

    assert exc_info.value.reason == "DHAN_RATE_LIMITED"
    assert ensure_calls == ["called"]


def test_ensure_token_fresh_can_spend_reserved_budget_on_profile_regen_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    service = DhanCredentialService()
    limiter = DhanRateLimiter(rate_per_second=0.0, capacity=3, burst_cap=3, reserved_capacity=3)
    now = datetime(2026, 3, 21, 4, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(dhan_credentials_module, "_api_rate_limiter", limiter)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_access_token", "expired-token")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_pin", "4321")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_totp_secret", "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_profile_check_seconds", 60)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_token_renewal_lead_seconds", 3600)

    service.reset_runtime_state()
    service.initialize(force_reload=True)
    service._client_id = "1103337749"
    service._access_token = "expired-token"
    service._expires_at = now + timedelta(hours=1)
    service._last_profile_checked_at = None

    calls: list[str] = []

    def fake_request_json(method: str, url: str, *, budget_operation: str | None = None, **kwargs):
        calls.append(f"{budget_operation}:{url.rsplit('/', 1)[-1]}")
        if url.endswith("/profile") and len([item for item in calls if item.startswith("profile:")]) == 1:
            raise DhanApiError("DHAN_AUTH_FAILED", "token expired", auth_failed=True)
        if url.endswith("/generateAccessToken"):
            return {
                "accessToken": "fresh-token",
                "expiryTime": "2026-03-22T10:00:00.000",
            }
        if url.endswith("/profile"):
            return {
                "dhanClientId": "1103337749",
                "tokenValidity": "22/03/2026 10:00",
                "dataPlan": "Active",
                "dataValidity": "2026-04-03 21:50:36.0",
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    assert service.ensure_token_fresh(force_profile=True) is True
    assert calls == [
        "profile:profile",
        "generate_access_token:generateAccessToken",
        "profile:profile",
    ]


def test_planned_renewal_prefers_active_token_renewal(monkeypatch: pytest.MonkeyPatch) -> None:
    service = DhanCredentialService()
    now = datetime(2026, 3, 21, 4, 0, tzinfo=timezone.utc)
    old_token = "active-token"
    new_token = "renewed-token"

    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_access_token", old_token)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_pin", "4321")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_totp_secret", "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_profile_check_seconds", 60)
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_token_renewal_lead_seconds", 3600)

    service.reset_runtime_state()
    service.initialize(force_reload=True)
    service._client_id = "1103337749"
    service._access_token = old_token
    service._expires_at = now + timedelta(minutes=20)
    service._last_profile_checked_at = now - timedelta(hours=1)

    calls: list[str] = []

    def fake_request_json(method: str, url: str, *, budget_operation: str | None = None, **kwargs):
        calls.append(f"{budget_operation}:{url.rsplit('/', 1)[-1]}")
        if url.endswith("/profile"):
            headers = kwargs.get("headers") or {}
            token = headers.get("access-token")
            validity = "21/03/2026 10:00" if token == old_token else "22/03/2026 10:00"
            return {
                "dhanClientId": "1103337749",
                "tokenValidity": validity,
                "dataPlan": "Active",
                "dataValidity": "2026-04-03 21:50:36.0",
            }
        if url.endswith("/RenewToken"):
            return {
                "accessToken": new_token,
                "expiryTime": "2026-03-22T10:00:00.000",
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    assert service.ensure_token_fresh(force_profile=True, allow_planned_renewal=True) is True
    assert calls == [
        "profile:profile",
        "renew_token:RenewToken",
        "profile:profile",
    ]
    assert service.snapshot().access_token == new_token
    assert service.snapshot().token_source == "renew"


def test_failed_totp_waits_for_next_window_not_two_minute_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    service = DhanCredentialService()
    clock = {"time": 1_000.0, "mono": 2_000.0}

    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_client_id", "1103337749")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_pin", "4321")
    monkeypatch.setattr(dhan_credentials_module.settings, "dhan_totp_secret", "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr(dhan_credentials_module.time, "time", lambda: clock["time"])
    monkeypatch.setattr(dhan_credentials_module.time, "monotonic", lambda: clock["mono"])

    def fake_sleep(seconds: float) -> None:
        clock["time"] += seconds
        clock["mono"] += seconds

    monkeypatch.setattr(dhan_credentials_module.time, "sleep", fake_sleep)
    monkeypatch.setattr(dhan_credentials_module, "_seconds_until_next_totp_window", lambda **kwargs: 0.5)

    service.reset_runtime_state()
    service._client_id = "1103337749"

    generate_calls = {"count": 0}

    def fake_request_json(method: str, url: str, *, budget_operation: str | None = None, **kwargs):
        if url.endswith("/generateAccessToken"):
            generate_calls["count"] += 1
            if generate_calls["count"] <= 5:
                return {"status": "error", "message": "Invalid TOTP"}
            return {
                "accessToken": "fresh-token",
                "expiryTime": "2026-03-22T10:00:00.000",
            }
        if url.endswith("/profile"):
            return {
                "dhanClientId": "1103337749",
                "tokenValidity": "22/03/2026 10:00",
                "dataPlan": "Active",
                "dataValidity": "2026-04-03 21:50:36.0",
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with service._renewal_lock:
        assert service._regenerate_via_totp_inner(reason="profile-check-failed") is True

    assert generate_calls["count"] == 6
    assert 2_000.5 <= clock["mono"] < 2_010.0
    assert service.snapshot().access_token == "fresh-token"


def test_request_json_redacts_auth_query_params_in_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    service = DhanCredentialService()

    class Response:
        status_code = 400
        text = '{"message":"Invalid TOTP"}'

        @staticmethod
        def json() -> dict[str, str]:
            return {"message": "Invalid TOTP"}

    monkeypatch.setattr(dhan_credentials_module.httpx, "request", lambda *args, **kwargs: Response())

    with pytest.raises(DhanApiError) as exc_info:
        service._request_json(
            "POST",
            "https://auth.dhan.co/app/generateAccessToken?dhanClientId=1103337749&pin=123456&totp=000000",
        )

    message = exc_info.value.message
    assert "generateAccessToken" in message
    assert "pin=123456" not in message
    assert "totp=000000" not in message
