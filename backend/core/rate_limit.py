"""
Minimal in-memory rate limiter for auth endpoints (register / login /
password-reset request) - the "critical" gap flagged in the roadmap review:
these endpoints had zero brute-force / credential-stuffing protection.

Deliberately stdlib-only (no slowapi/redis/etc): this repo has no cache/
queue infra yet, and pulling in a new dependency that can't be verified to
install in every environment this runs in (see security.py's same reasoning
for PBKDF2-over-bcrypt) is worse than a small self-contained limiter.

Scope / honest limitations:
  - Per-process, in-memory. Restarting the app clears all counters, and this
    does NOT share state across multiple worker processes/instances - fine
    for a single-instance deployment (which is all this app supports today,
    single SQLite file), but if you ever run this behind >1 uvicorn worker
    or multiple replicas, swap `_hits` for a shared store (Redis, the SQL DB
    itself, etc). The limiter is intentionally isolated behind one small
    interface (`check`) so that swap doesn't touch any route code.
  - Keyed by client IP (`request.client.host`) + a per-purpose bucket name,
    so login attempts against different accounts from the same IP still
    share one budget (this is what stops credential stuffing) while a
    register-spam attempt and a login-brute-force attempt are tracked
    separately.
  - Sliding window via a deque of timestamps, not a token bucket - simpler,
    and "N attempts per window" is exactly the semantics we want here.
"""
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Tuple

from fastapi import HTTPException, Request, status


class _RateLimiter:
    def __init__(self) -> None:
        self._hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, bucket: str, max_attempts: int, window_seconds: int) -> None:
        now = time.monotonic()
        slot = (bucket, key)
        with self._lock:
            hits = self._hits[slot]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= max_attempts:
                retry_after = max(1, int(window_seconds - (now - hits[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please wait before trying again.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)


_limiter = _RateLimiter()


def _client_key(request: Request) -> str:
    # Behind a reverse proxy (Render, Cloud Run, nginx, ...) request.client
    # is the PROXY's own address, not the visitor's - every single user
    # collapses onto one IP, so the whole app effectively shares one login/
    # register budget instead of each visitor getting their own. That's why
    # signup/login would start failing with "Too many attempts" for
    # everyone after only a handful of real users tried it, even though the
    # limiter itself was working exactly as designed. Trust the standard
    # X-Forwarded-For header (set by every major PaaS/proxy) and use the
    # FIRST address in it - that's the original client, appended by the
    # first hop; anything a downstream proxy added is later in the list.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    # Fall back to the direct connection's address (local dev / no proxy),
    # then a constant bucket rather than crashing if even that's missing
    # (fails open to "everyone shares one budget" instead of 500ing).
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, max_attempts: int, window_seconds: int):
    """FastAPI dependency factory - use as
    `Depends(rate_limit("login", max_attempts=10, window_seconds=60))`."""

    def _dependency(request: Request) -> None:
        _limiter.check(_client_key(request), bucket, max_attempts, window_seconds)

    return _dependency
