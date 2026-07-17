from redis.asyncio import Redis


class RateLimiter:
    """Shared fixed-window rate limiter, keyed generically so any
    public-facing route can reuse it (see Decision D14)."""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def check_and_increment(self, key: str, limit: int, window_seconds: int) -> bool:
        redis_key = f"ratelimit:{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, window_seconds)
        return count <= limit
