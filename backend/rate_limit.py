from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from collections.abc import Callable
from threading import Lock

from fastapi import HTTPException, Request, Response, status


_rate_buckets: dict[str, list[float]] = defaultdict(list)
_rate_lock = Lock()


def _rate_subject(request: Request) -> str:
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api:{api_key[:12]}"
    authorization = request.headers.get("Authorization")
    if authorization:
        digest = hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:16]
        return f"auth:{digest}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def _rate_headers(*, limit: int, remaining: int, reset_at: int) -> dict[str, str]:
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(remaining, 0)),
        "X-RateLimit-Reset": str(reset_at),
    }


def rate_limit(bucket: str, max_requests: int, window_seconds: int) -> Callable:
    def dependency(request: Request, response: Response) -> None:
        now = time.time()
        key = f"{bucket}:{_rate_subject(request)}"
        with _rate_lock:
            expired: list[str] = []
            for bucket_key, values in list(_rate_buckets.items()):
                fresh = [stamp for stamp in values if now - stamp < window_seconds]
                if fresh:
                    _rate_buckets[bucket_key] = fresh
                else:
                    expired.append(bucket_key)
            for bucket_key in expired:
                _rate_buckets.pop(bucket_key, None)

            timestamps = [stamp for stamp in _rate_buckets[key] if now - stamp < window_seconds]
            if len(timestamps) >= max_requests:
                reset_at = int((timestamps[0] if timestamps else now) + window_seconds)
                headers = _rate_headers(limit=max_requests, remaining=0, reset_at=reset_at)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers=headers,
                )
            timestamps.append(now)
            _rate_buckets[key] = timestamps
            reset_at = int((timestamps[0] if timestamps else now) + window_seconds)
            headers = _rate_headers(limit=max_requests, remaining=max_requests - len(timestamps), reset_at=reset_at)
            for header, value in headers.items():
                response.headers[header] = value

    dependency.__lite_rate_limit__ = {
        "bucket": bucket,
        "limit": max_requests,
        "window_seconds": window_seconds,
    }

    return dependency
