"""
ResQAI - Rate Limiting Middleware
Token bucket rate limiting using Redis with per-user and per-IP strategies.
"""

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Endpoints exempt from rate limiting
EXEMPT_PATHS = {"/health", "/health/detailed", "/metrics", "/docs", "/redoc", "/openapi.json"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis sliding window counter.
    Limits are applied per authenticated user (or IP for anonymous requests).
    Returns HTTP 429 when limit is exceeded with Retry-After header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        try:
            from app.core.redis_client import get_redis
            redis = get_redis()

            if redis is None:
                # Redis unavailable — fail open (allow all requests)
                return await call_next(request)

            # Determine rate limit identifier: user ID > API key > IP
            identifier = self._get_identifier(request)
            limit = settings.RATE_LIMIT_REQUESTS
            window = settings.RATE_LIMIT_WINDOW_SECONDS

            # Redis sliding window counter
            key = f"rate_limit:{identifier}"
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, window)

            ttl = await redis.ttl(key)
            remaining = max(0, limit - current)
            reset_at = int(time.time()) + max(ttl, 0)

            if current > limit:
                logger.warning(
                    f"Rate limit exceeded",
                    identifier=identifier,
                    count=current,
                    limit=limit,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": 429,
                            "message": "Too many requests. Please slow down.",
                            "type": "rate_limit_exceeded",
                        }
                    },
                    headers={
                        "X-Rate-Limit-Limit": str(limit),
                        "X-Rate-Limit-Remaining": "0",
                        "X-Rate-Limit-Reset": str(reset_at),
                        "Retry-After": str(max(ttl, 1)),
                    },
                )

            response = await call_next(request)
            response.headers["X-Rate-Limit-Limit"] = str(limit)
            response.headers["X-Rate-Limit-Remaining"] = str(remaining)
            response.headers["X-Rate-Limit-Reset"] = str(reset_at)
            return response

        except Exception as e:
            # If Redis is unavailable, fail open (allow the request)
            logger.error(f"Rate limiter error (failing open): {e}")
            return await call_next(request)

    def _get_identifier(self, request: Request) -> str:
        """
        Build the rate limit identifier in priority order:
        1. Authenticated user ID (from JWT)
        2. API key header
        3. Client IP address
        """
        # Try to extract user from JWT without raising (middleware runs before auth)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from app.core.security import decode_token, TokenType
                token = auth_header[7:]
                payload = decode_token(token)
                if payload.get("type") == TokenType.ACCESS:
                    return f"user:{payload['sub']}"
            except Exception:
                pass

        # API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"apikey:{api_key[:16]}"

        # Fall back to IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"
        return f"ip:{request.client.host if request.client else 'unknown'}"
