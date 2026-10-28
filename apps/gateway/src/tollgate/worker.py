import asyncio
import json
import logging
import time

from redis.exceptions import ResponseError

logger = logging.getLogger("tollgate.worker")


async def run_worker(repo, fast, once=False):
    if not fast.redis:
        raise RuntimeError("Worker requires TOLLGATE_REDIS_URL")
    redis = fast.redis
    try:
        await redis.xgroup_create("tollgate:events", "ledger", id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    # Reclaim stale unacknowledged events after a worker crash. Inserts are idempotent.
    import os
    import uuid

    consumer = "worker-" + str(os.getpid()) + "-" + uuid.uuid4().hex
    last_reconcile = 0.0
    last_notifications = 0.0
    notification_task = None
    while True:
        if time.monotonic() - last_reconcile > 180:
            await reconcile(repo, fast)
            last_reconcile = time.monotonic()
        claimed = await redis.xautoclaim("tollgate:events", "ledger", consumer, 30000, "0-0", count=500)
        batches = [("tollgate:events", claimed[1])] if claimed[1] else []
        if not batches:
            batches = await redis.xreadgroup(
                "ledger", consumer, {"tollgate:events": ">"}, count=500, block=1000
            )
        for _, messages in batches:
            for id, fields in messages:
                try:
                    await repo.write_event(json.loads(fields["event"]))
                    await redis.xack("tollgate:events", "ledger", id)
                except (ValueError, KeyError, TypeError):
                    await redis.xadd(
                        "tollgate:dead-letter", {"source_id": id, "error": "invalid_event"}, maxlen=1000
                    )
                    await redis.xack("tollgate:events", "ledger", id)
                    await redis.xdel("tollgate:events", id)
                    logger.error("Malformed event %s quarantined without payload", id)
                except Exception:
                    logger.exception("Ledger write failed; event retained for retry")
                    await asyncio.sleep(0.2)
        await redis.set("tollgate:worker-heartbeat", str(time.time()), ex=60)
        if time.monotonic() - last_notifications > 15 and (
            notification_task is None or notification_task.done()
        ):
            if notification_task is not None:
                try:
                    notification_task.result()
                except Exception:
                    logger.error("Notification background task failed; pending delivery retained")
            import base64

            from .config import Settings
            from .notifications import deliver
            from .security import Crypto, digest

            config = Settings()
            crypto = Crypto(
                config.master_key
                or base64.b64encode(bytes.fromhex(digest("tollgate-local-demo-only"))).decode()
            )

            async def notifications():
                for tenant in await repo.records("tenant", "global"):
                    await deliver(repo, crypto, tenant["name"])

            if once:
                await notifications()
            else:
                notification_task = asyncio.create_task(notifications())
            last_notifications = time.monotonic()

        if once:
            return


async def reconcile(repo, fast):
    """Freeze new settlements briefly, rebuild settled spend, preserve in-flight reservations.

    Include stream events not yet in the repeatable-read ledger snapshot. This avoids
    losing charges while the worker catches up. The global lease is also checked by
    reservation and settlement Lua scripts.
    """
    import secrets

    token = secrets.token_hex(16)
    redis = fast.redis
    if not await redis.set("tollgate:reconcile-lock", token, nx=True, ex=30):
        return
    try:
        recovering = await repo.recovery_records()
        totals, ids = await repo.ledger_snapshot()
        for _, fields in await redis.xrange("tollgate:events"):
            try:
                event = json.loads(fields["event"])
                if not all(k in event for k in ("id", "tenant_id", "customer_id", "created_at", "cost")):
                    continue
            except (ValueError, KeyError, TypeError):
                continue
            if event["id"] not in ids:
                key = f"{event['tenant_id']}:{event['customer_id']}:{event['created_at'][:7]}"
                totals[key] = totals.get(key, 0) + event["cost"]
        # Compare lease value in the same atomic operation as the writes. Never commit
        # an old snapshot after a long-running query outlives the admission freeze.
        async for key in redis.scan_iter(match="spend:*"):
            totals.setdefault(key.removeprefix("spend:"), 0)
        args = [token]
        for key, cost in totals.items():
            args.extend(["spend:" + key, cost])
        committed = await redis.eval(
            """
            if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
            for i=2,#ARGV,2 do redis.call('SET', ARGV[i], ARGV[i+1]) end
            redis.call('DEL', KEYS[1])
            return 1
        """,
            1,
            "tollgate:reconcile-lock",
            *args,
        )
        if committed:
            for row in recovering:
                await repo.delete("recovery", row["id"], row["tenant_id"])
    finally:
        await redis.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0",
            1,
            "tollgate:reconcile-lock",
            token,
        )
