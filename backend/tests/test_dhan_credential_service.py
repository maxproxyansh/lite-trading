from __future__ import annotations

import pytest

from services.dhan_credential_service import (
    DhanApiError,
    DhanCredentialService,
    DhanRateLimiter,
    _classify_dhan_error,
)


@pytest.mark.parametrize(
    ("code", "message", "status", "expected_reason", "expected_auth"),
    [
        ("807", "Access token is expired", 401, "DHAN_AUTH_FAILED", True),
        ("808", "Authentication Failed - Client ID or Access Token invalid", 401, "DHAN_AUTH_FAILED", True),
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
