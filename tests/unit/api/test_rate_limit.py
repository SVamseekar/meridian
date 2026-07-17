import pytest
from fakeredis.aioredis import FakeRedis

from meridian.api.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_first_request_is_allowed():
    redis = FakeRedis()
    limiter = RateLimiter(redis)
    allowed = await limiter.check_and_increment("tenant-a", limit=2, window_seconds=60)
    assert allowed is True


@pytest.mark.asyncio
async def test_requests_within_limit_are_allowed():
    redis = FakeRedis()
    limiter = RateLimiter(redis)
    assert await limiter.check_and_increment("tenant-a", limit=2, window_seconds=60) is True
    assert await limiter.check_and_increment("tenant-a", limit=2, window_seconds=60) is True


@pytest.mark.asyncio
async def test_request_over_limit_is_rejected():
    redis = FakeRedis()
    limiter = RateLimiter(redis)
    await limiter.check_and_increment("tenant-a", limit=2, window_seconds=60)
    await limiter.check_and_increment("tenant-a", limit=2, window_seconds=60)
    allowed = await limiter.check_and_increment("tenant-a", limit=2, window_seconds=60)
    assert allowed is False


@pytest.mark.asyncio
async def test_different_keys_have_independent_limits():
    redis = FakeRedis()
    limiter = RateLimiter(redis)
    await limiter.check_and_increment("tenant-a", limit=1, window_seconds=60)
    allowed_b = await limiter.check_and_increment("tenant-b", limit=1, window_seconds=60)
    assert allowed_b is True
