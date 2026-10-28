import asyncio
import os
import uuid

import pytest
from tollgate.fastpath import BudgetExhausted, FastPath


@pytest.fixture(params=["memory", "redis"])
async def fast(request):
    if request.param == "redis" and not os.getenv("TEST_REDIS_URL"):
        pytest.skip("Set TEST_REDIS_URL to run real Redis tests")
    value = FastPath(os.getenv("TEST_REDIS_URL", "") if request.param == "redis" else "")
    yield value
    if value.redis:
        await value.redis.aclose()


async def test_300_concurrent_reservations_never_overspend(fast):
    key = "test:" + uuid.uuid4().hex
    await fast.initialize(key, 0)

    async def request(i):
        id = str(i)
        try:
            await fast.reserve(key, id, 100000, [], [1000])
            await asyncio.sleep(0.001)
            await fast.settle(key, id, 1000)
            return True
        except BudgetExhausted:
            return False

    accepted = sum(await asyncio.gather(*(request(i) for i in range(300))))
    assert accepted == 100
    assert await fast.spend(key) == 100000


async def test_degradation_quality_lock_and_overage(fast):
    key = "test:" + uuid.uuid4().hex
    await fast.initialize(key, 85)
    steps = [{"at": 0.8, "tier": 1}, {"at": 0.95, "tier": 2}]
    assert (await fast.reserve(key, "a", 100, steps, [10, 5, 1]))[0] == 1
    await fast.settle(key, "a", 5)
    assert (await fast.reserve(key, "b", 100, steps, [10, 5, 1], allow=False))[0] == 0
    await fast.settle(key, "b", 10)
    with pytest.raises(BudgetExhausted):
        await fast.reserve(key, "c", 100, steps, [10, 5, 1])
    assert (await fast.reserve(key, "d", 100, steps, [10, 5, 1], policy="allow_overage", overage=5))[0] == 2


async def test_settlement_idempotent(fast):
    key = "test:" + uuid.uuid4().hex
    await fast.initialize(key, 0)
    await fast.reserve(key, "a", 100, [], [10])
    await fast.settle(key, "a", 5)
    await fast.settle(key, "a", 5)
    assert await fast.spend(key) == 5


async def test_atomic_rate_limit_and_cache(fast):
    key = "test:" + uuid.uuid4().hex
    assert await fast.rate_limit([key, key + "tenant"], [2, 3])
    assert await fast.rate_limit([key, key + "tenant"], [2, 3])
    assert not await fast.rate_limit([key, key + "tenant"], [2, 3])
    await fast.cache_put(key, {"text": "[EMAIL_1]"})
    assert await fast.cached(key) == {"text": "[EMAIL_1]"}


async def test_circuit_breaker(fast):
    key = "test:" + uuid.uuid4().hex
    for _ in range(5):
        await fast.failure(key)
    assert await fast.breaker_open(key)


async def test_inflight_limits_release_capacity(fast):
    key = "test-concurrency-" + uuid.uuid4().hex
    assert await fast.acquire(key, "one", 1)
    assert not await fast.acquire(key, "two", 1)
    await fast.release(key, "one")
    assert await fast.acquire(key, "two", 1)
    await fast.release(key, "two")
