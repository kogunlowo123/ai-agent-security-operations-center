"""Token-bucket rate limiting middleware for the AI Agent SOC API."""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Rate limits per path prefix (requests per minute)
PATH_RATE_LIMITS: dict[str, int] = {
    "/api/v1/events/ingest": 1000,
    "/api/v1/posture": 60,
    "/api/v1/hunt": 100,
    "/api/v1/incidents": 100,
}
DEFAULT_RATE_LIMIT = 300

AUTH_BYPASS_PATHS = frozenset(["/api/v1/health", "/api/v1/readiness"])


def _get_limit(path: str) -> int:
    for prefix, limit in PATH_RATE_LIMITS.items():
        if path.startswith(prefix):
            return limit
    return DEFAULT_RATE_LIMIT


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token-bucket rate limiting per tenant.

    Uses Redis for distributed rate limiting when available;
    falls back to in-process memory for development.
    """

    def __init__(self, app, redis_client=None):
        super().__init__(app)
        self._redis = redis_client
        self._local_buckets: dict[str, tuple[float, float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in AUTH_BYPASS_PATHS:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", "anonymous")
        limit = _get_limit(request.url.path)
        key = f"ratelimit:{tenant_id}:{request.url.path.split('/')[3]}"

        allowed = await self._check_rate_limit(key, limit)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please retry after 60 seconds."},
                headers={"Retry-After": "60", "X-RateLimit-Limit": str(limit)},
            )

        return await call_next(request)

    async def _check_rate_limit(self, key: str, limit: int) -> bool:
        """Check using Redis sliding window if available, else in-process token bucket."""
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                now = time.time()
                window_start = now - 60
                pipe.zremrangebyscore(key, "-inf", window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, 120)
                results = pipe.execute()
                count = results[2]
                return count <= limit
            except Exception as exc:
                logger.warning("Redis rate limit check failed: %s; allowing request", exc)
                return True

        # In-process fallback
        now = time.time()
        tokens, last_refill = self._local_buckets.get(key, (float(limit), now))
        elapsed = now - last_refill
        tokens = min(float(limit), tokens + elapsed * (limit / 60.0))
        if tokens >= 1.0:
            self._local_buckets[key] = (tokens - 1.0, now)
            return True
        self._local_buckets[key] = (tokens, now)
        return False
