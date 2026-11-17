"""Process-local abuse throttle for sensitive API routes.

This is NOT distributed, multi-worker, or production-grade edge protection.
It reduces accidental local hammering and provides a fail-closed hook for tests.
Disable with OYDP_RATE_LIMIT=0. Tune with OYDP_RATE_LIMIT_WINDOW_SECONDS and
OYDP_RATE_LIMIT_MAX (requests per window per caller key).
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

_DEFAULT_WINDOW = 60
_DEFAULT_MAX = 120
_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def rate_limit_enabled() -> bool:
    return os.getenv('OYDP_RATE_LIMIT', '1') != '0'


def _window_seconds() -> int:
    raw = os.getenv('OYDP_RATE_LIMIT_WINDOW_SECONDS', str(_DEFAULT_WINDOW)).strip()
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise HTTPException(503, 'Invalid rate limit configuration') from exc
    if value < 1:
        raise HTTPException(503, 'Invalid rate limit configuration')
    return value


def _max_requests() -> int:
    raw = os.getenv('OYDP_RATE_LIMIT_MAX', str(_DEFAULT_MAX)).strip()
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise HTTPException(503, 'Invalid rate limit configuration') from exc
    if value < 1:
        raise HTTPException(503, 'Invalid rate limit configuration')
    return value


def _caller_key(request: Request, authorization: str | None) -> str:
    if authorization and authorization.strip():
        digest = hashlib.sha256(authorization.strip().encode('utf-8')).hexdigest()[:32]
        return f'token:{digest}'
    host = request.client.host if request.client else 'unknown'
    return f'ip:{host}'


def reset_rate_limit_state() -> None:
    """Test helper: clear process-local buckets."""
    with _lock:
        _buckets.clear()


def enforce_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None),
) -> bool:
    """Reject with 429 when the caller exceeds the configured window budget."""
    if not rate_limit_enabled():
        return True
    window = _window_seconds()
    limit = _max_requests()
    now = time.monotonic()
    key = f'{_caller_key(request, authorization)}|{request.method}|{request.url.path}'
    with _lock:
        bucket = _buckets[key]
        while bucket and now - bucket[0] >= window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, 'Too many requests')
        bucket.append(now)
    return True
