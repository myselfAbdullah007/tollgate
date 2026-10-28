import asyncio
import json
import time
from collections import defaultdict, deque
from collections.abc import Awaitable
from pathlib import Path
from typing import Any, cast

from redis.asyncio import Redis

LUA = Path(__file__).parent / "lua"


async def evaluate(redis, script, key_count, *args):
    for _ in range(350):
        result = await cast(Awaitable[Any], redis.eval(script, key_count, *args))
        if result == -2 or isinstance(result, list) and result[0] == -2:
            await asyncio.sleep(0.1)
            continue
        return result
    raise RuntimeError("Spend reconciliation did not release its lease")


class BudgetExhausted(Exception):
    pass


class FastPath:
    """Redis in deployments; the single-process demo uses the same semantics under a lock."""

    def __init__(self, redis_url=""):
        self.redis = Redis.from_url(redis_url, decode_responses=True) if redis_url else None
        self.lock = asyncio.Lock()
        self.spends: dict[str, int] = {}
        self.reservations: dict[str, dict] = defaultdict(dict)
        self.rates: dict[str, deque] = defaultdict(deque)
        self.cache: dict[str, tuple] = {}
        self.failures: dict[str, list] = defaultdict(list)

    async def initialize(self, key, ledger):
        if self.redis:
            await self.redis.set("spend:" + key, ledger, nx=True)
        else:
            self.spends.setdefault(key, ledger)

    async def spend(self, key):
        if self.redis:
            return int(await self.redis.get("spend:" + key) or 0)
        return self.spends.get(key, 0)

    async def reserve(
        self, key, request_id, budget, thresholds, estimates, allow=True, policy="block", overage=0
    ):
        if self.redis:
            result = await evaluate(
                self.redis,
                (LUA / "reserve.lua").read_text(),
                3,
                "spend:" + key,
                "reserved:" + key,
                "deadlines:" + key,
                time.time(),
                request_id,
                budget,
                json.dumps(thresholds),
                json.dumps(estimates),
                str(allow).lower(),
                policy,
                overage,
            )
            if result[0] == -1:
                raise BudgetExhausted()
            return tuple(result)
        async with self.lock:
            now = time.time()
            self.reservations[key] = {k: v for k, v in self.reservations[key].items() if v[1] > now}
            used = self.spends.get(key, 0) + sum(v[0] for v in self.reservations[key].values())
            tier = max([0] + [s["tier"] for s in thresholds if allow and used >= budget * s["at"]])
            tier = min(tier, len(estimates) - 1)
            est = estimates[tier]
            if used + est > budget + (overage if policy == "allow_overage" else 0):
                raise BudgetExhausted()
            self.reservations[key][request_id] = (est, now + 180)
            return tier, used, est

    async def settle(self, key, request_id, actual, event=None):
        if self.redis:
            # Cost and event are committed atomically; retry cannot charge twice.
            return await evaluate(
                self.redis,
                """
                if redis.call('EXISTS', 'tollgate:reconcile-lock') == 1 then return -2 end
                if redis.call('HDEL', KEYS[2], ARGV[1]) == 0 then return 0 end
                redis.call('ZREM', KEYS[3], ARGV[1])
                redis.call('INCRBY', KEYS[1], ARGV[2])
                if ARGV[3] ~= '' then redis.call('XADD', KEYS[4], '*', 'event', ARGV[3]) end
                return 1
            """,
                4,
                "spend:" + key,
                "reserved:" + key,
                "deadlines:" + key,
                "tollgate:events",
                request_id,
                actual,
                json.dumps(event) if event else "",
            )
        async with self.lock:
            if self.reservations[key].pop(request_id, None) is None:
                return False
            self.spends[key] = self.spends.get(key, 0) + actual
            return True

    async def rate_limit(self, keys, limits):
        now = time.time()
        if self.redis:
            import uuid

            return bool(
                await evaluate(
                    self.redis,
                    (LUA / "rate.lua").read_text(),
                    len(keys),
                    *["rate:" + k for k in keys],
                    now,
                    str(uuid.uuid4()),
                    *limits,
                )
            )
        async with self.lock:
            for key in keys:
                while self.rates[key] and self.rates[key][0] <= now - 60:
                    self.rates[key].popleft()
            if any(len(self.rates[k]) >= limit for k, limit in zip(keys, limits)):
                return False
            for key in keys:
                self.rates[key].append(now)
            return True

    async def cached(self, key):
        if self.redis:
            raw = await self.redis.get("cache:" + key)
            return json.loads(raw) if raw else None
        item = self.cache.get(key)
        return item[0] if item and item[1] > time.time() else None

    async def cache_put(self, key, value):
        if self.redis:
            await self.redis.set("cache:" + key, json.dumps(value), ex=3600)
        else:
            if len(self.cache) > 10000:
                self.cache.clear()
            self.cache[key] = (value, time.time() + 3600)

    async def breaker_open(self, target):
        if self.redis:
            return bool(await self.redis.exists("breaker:" + target))
        return len([t for t in self.failures[target] if t > time.time() - 30]) >= 5

    async def failure(self, target):
        if self.redis:
            count = await self.redis.incr("failures:" + target)
            if count == 1:
                await self.redis.expire("failures:" + target, 30)
            if count >= 5:
                await self.redis.set("breaker:" + target, "1", ex=30)
        else:
            self.failures[target] = [t for t in self.failures[target] if t > time.time() - 30] + [time.time()]

    async def success(self, target):
        if self.redis:
            await self.redis.delete("failures:" + target)
        else:
            self.failures.pop(target, None)
