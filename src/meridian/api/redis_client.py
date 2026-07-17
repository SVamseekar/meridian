import os

from redis.asyncio import Redis

_redis: Redis | None = None


def get_redis_url() -> str:
    return os.environ["REDIS_URL"]


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_redis_url())
    return _redis
