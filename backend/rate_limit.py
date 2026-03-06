from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import HTTPException, Request, status


_rate_buckets: dict[str, list[float]] = defaultdict(list)


def rate_limit(bucket: str, max_requests: int, window_seconds: int) -> Callable:
    def dependency(request: Request) -> None:
        now = time.time()
        client = request.client.host if request.client else "unknown"
        key = f"{bucket}:{client}"
        timestamps = [stamp for stamp in _rate_buckets[key] if now - stamp < window_seconds]
        if len(timestamps) >= max_requests:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        timestamps.append(now)
        _rate_buckets[key] = timestamps

    return dependency
