"""
ResQAI - Redis Client
Async Redis client with connection pooling, pub/sub, and caching utilities.
"""

import json
from typing import Any, Optional, Union
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from redis.asyncio import Redis, ConnectionPool
from loguru import logger

from app.config import settings


# -------------------------------------------------------
# Connection Pool
# -------------------------------------------------------
_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


async def init_redis() -> None:
    """Initialize Redis connection pool. Non-fatal if Redis is unavailable."""
    global _redis_pool, _redis_client
    try:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.redis.URL,
            max_connections=50,
            decode_responses=True,
            health_check_interval=30,
        )
        _redis_client = aioredis.Redis(connection_pool=_redis_pool)
        await _redis_client.ping()
        logger.info("Redis connection established", url=settings.redis.URL.split("@")[-1])
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Running without cache.")
        _redis_client = None
        _redis_pool = None


async def close_redis() -> None:
    """Close Redis connections gracefully."""
    global _redis_pool, _redis_client
    if _redis_client:
        await _redis_client.aclose()
    if _redis_pool:
        await _redis_pool.aclose()
    logger.info("Redis connections closed")


def get_redis() -> Optional[Redis]:
    """
    Get the Redis client instance.
    Returns None if Redis is not initialized (graceful degradation).
    """
    return _redis_client


def get_cache_manager() -> "CacheManager":
    """FastAPI dependency: get cache manager instance."""
    return CacheManager(get_redis())


# -------------------------------------------------------
# Cache Utilities
# -------------------------------------------------------
class CacheManager:
    """
    High-level Redis cache manager with serialization and TTL management.
    Gracefully degrades (no-op) when Redis is unavailable.
    """

    def __init__(self, client: Optional[Redis], prefix: str = "resqai"):
        self._client = client
        self._prefix = prefix

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        if not self._client:
            return None
        raw = await self._client.get(self._make_key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(self, key: str, value: Any, ttl: int = settings.redis.CACHE_TTL) -> None:
        if not self._client:
            return
        serialized = json.dumps(value, default=str)
        await self._client.setex(self._make_key(key), ttl, serialized)

    async def delete(self, key: str) -> int:
        if not self._client:
            return 0
        return await self._client.delete(self._make_key(key))

    async def delete_pattern(self, pattern: str) -> int:
        if not self._client:
            return 0
        full_pattern = f"{self._prefix}:{pattern}"
        keys = await self._client.keys(full_pattern)
        if keys:
            return await self._client.delete(*keys)
        return 0

    async def exists(self, key: str) -> bool:
        if not self._client:
            return False
        return bool(await self._client.exists(self._make_key(key)))

    async def expire(self, key: str, ttl: int) -> bool:
        if not self._client:
            return False
        return bool(await self._client.expire(self._make_key(key), ttl))

    async def increment(self, key: str, amount: int = 1) -> int:
        if not self._client:
            return 0
        return await self._client.incrby(self._make_key(key), amount)

    async def get_or_set(self, key: str, factory, ttl: int = settings.redis.CACHE_TTL) -> Any:
        if not self._client:
            return await factory()
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await factory()
        await self.set(key, value, ttl)
        return value

    async def health_check(self) -> dict:
        if not self._client:
            return {"status": "unavailable", "error": "Redis not connected"}
        try:
            info = await self._client.info("server")
            return {
                "status": "healthy",
                "version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# -------------------------------------------------------
# Pub/Sub Manager
# -------------------------------------------------------
class PubSubManager:
    """
    Redis Pub/Sub manager for real-time event broadcasting.
    Used for WebSocket event distribution across multiple backend instances.
    """

    def __init__(self, client: Redis):
        self._client = client

    async def publish(self, channel: str, message: Any) -> int:
        """
        Publish a message to a Redis channel.

        Args:
            channel: Channel name
            message: Message payload (will be JSON serialized)

        Returns:
            Number of subscribers that received the message
        """
        payload = json.dumps(message, default=str)
        return await self._client.publish(channel, payload)

    @asynccontextmanager
    async def subscribe(self, *channels: str):
        """
        Context manager for subscribing to channels.

        Usage:
            async with pubsub.subscribe("channel1", "channel2") as sub:
                async for message in sub.listen():
                    ...
        """
        pubsub = self._client.pubsub()
        await pubsub.subscribe(*channels)
        try:
            yield pubsub
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()


# -------------------------------------------------------
# Rate Limiter
# -------------------------------------------------------
class RateLimiter:
    """
    Token bucket rate limiter using Redis.
    Used by the API middleware for request rate limiting.
    """

    def __init__(self, client: Redis):
        self._client = client

    async def is_allowed(
        self,
        identifier: str,
        limit: int = settings.RATE_LIMIT_REQUESTS,
        window: int = settings.RATE_LIMIT_WINDOW_SECONDS,
    ) -> tuple[bool, int]:
        """
        Check if a request is within rate limits.

        Args:
            identifier: Unique identifier (e.g., user ID, IP address)
            limit: Maximum requests per window
            window: Window size in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        key = f"rate_limit:{identifier}"
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        results = await pipe.execute()

        current_count = results[0]
        remaining = max(0, limit - current_count)
        allowed = current_count <= limit

        return allowed, remaining


# -------------------------------------------------------
# Module-level helpers
# -------------------------------------------------------
def get_cache_manager() -> CacheManager:
    """FastAPI dependency: get cache manager instance."""
    return CacheManager(get_redis())


def get_pubsub_manager() -> PubSubManager:
    """FastAPI dependency: get pub/sub manager instance."""
    return PubSubManager(get_redis())


def get_rate_limiter() -> RateLimiter:
    """FastAPI dependency: get rate limiter instance."""
    return RateLimiter(get_redis())
