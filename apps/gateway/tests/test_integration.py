"""Real PostgreSQL/Redis tests. Only the dedicated Tollgate services are used."""

import json
import os
import uuid

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from tollgate.config import Settings
from tollgate.main import create_app
from tollgate.worker import reconcile, run_worker


@pytest.fixture
async def integration_app():
    url = os.getenv("TEST_DATABASE_URL")
    redis = os.getenv("TEST_REDIS_URL")
    if not url or not redis:
        pytest.skip("Set TEST_DATABASE_URL and TEST_REDIS_URL for real infrastructure tests")
    database_name = "tollgate_test_" + uuid.uuid4().hex
    connection = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    await connection.execute(f"CREATE DATABASE {database_name}")
    target = url.rsplit("/", 1)[0] + "/" + database_name
    app = create_app(Settings(demo=True, database_url=target, redis_url=redis))
    try:
        async with app.router.lifespan_context(app):
            yield app
    finally:
        await connection.execute(f"DROP DATABASE {database_name} WITH (FORCE)")
        await connection.close()


async def test_postgres_partition_worker_and_no_pii(integration_app):
    app = integration_app
    tenant = "test-" + uuid.uuid4().hex
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post(
            "/admin/v1/auth/login", json={"email": "admin@tollgate.local", "password": "tollgate-demo-2026"}
        )
        c.headers["X-Tollgate-Admin"] = "1"
        r = await c.post("/admin/v1/tenants", json={"name": tenant, "display_name": "Integration"})
        assert r.status_code == 200, r.text
        r = await c.post(f"/admin/v1/tenants/{tenant}/keys", json={"name": "integration"})
        headers = {"Authorization": "Bearer " + r.json()["key"], "X-Tollgate-Customer": "customer"}
        r = await c.post(
            "/v1/chat/completions",
            headers=headers,
            json={
                "model": "smart",
                "temperature": 0,
                "messages": [{"role": "user", "content": "Email integration@example.com"}],
            },
        )
        assert r.status_code == 200, r.text
        assert "integration@example.com" in r.text
        from datetime import UTC, datetime

        spend_key = f"{tenant}:customer:{datetime.now(UTC).strftime('%Y-%m')}"
        await app.state.fast.redis.set("spend:" + spend_key, 0)
        await reconcile(app.state.repo, app.state.fast)
        assert await app.state.fast.spend(spend_key) > 0  # includes undelivered stream events
        await run_worker(app.state.repo, app.state.fast, once=True)
        logs = await app.state.repo.logs(tenant)
        assert len(logs) == 1
        assert logs[0]["pii_counts"]["EMAIL"] == 1
        assert "integration@example.com" not in json.dumps(logs)
        async with app.state.repo.db.session() as s:
            partitions = (
                await s.execute(
                    text("SELECT tablename FROM pg_tables WHERE tablename LIKE 'request_logs_20%'")
                )
            ).all()
            assert partitions
        # Replaying the same event must never double-charge the ledger or daily rollup.
        await app.state.repo.write_event(logs[0])
        assert len(await app.state.repo.logs(tenant)) == 1
        assert sum(d["requests"] for d in await app.state.repo.daily(tenant)) == 1
        for key in await app.state.fast.redis.keys("cache:*"):
            assert "integration@example.com" not in (await app.state.fast.redis.get(key))
        stream = await app.state.fast.redis.xrange("tollgate:events")
        assert "integration@example.com" not in json.dumps(stream)


async def test_reconcile_clears_drift_without_erasing_reservations(integration_app):
    from tollgate.worker import reconcile

    app = integration_app
    key = "audit-" + uuid.uuid4().hex + ":no-ledger:2026-10"
    await app.state.fast.initialize(key, 999)
    await app.state.fast.reserve(key, "active", 10000, [], [100])
    await reconcile(app.state.repo, app.state.fast)
    assert await app.state.fast.spend(key) == 0
    assert await app.state.fast.reserved(key) == 100
    await app.state.fast.settle(key, "active", 0)


async def test_malformed_stream_event_does_not_stop_delivery(integration_app):
    app = integration_app
    id = await app.state.fast.redis.xadd("tollgate:events", {"event": "not-json"})
    await run_worker(app.state.repo, app.state.fast, once=True)
    dead = await app.state.fast.redis.xrange("tollgate:dead-letter")
    assert any(fields["source_id"] == id for _, fields in dead)
    assert not await app.state.fast.redis.xrange("tollgate:events", min=id, max=id)


async def test_retention_deletes_only_committed_deliveries(integration_app):
    from tollgate.db import now, uid
    from tollgate.worker import prune_committed

    app = integration_app
    redis, repo = app.state.fast.redis, app.state.repo
    await run_worker(repo, app.state.fast, once=True)
    event = (await repo.logs())[0].copy()
    event.update(id=uid(), created_at=now(), customer_id="retention-" + uuid.uuid4().hex, cost=123)
    committed = await redis.xadd("tollgate:events", {"event": json.dumps(event)})
    await repo.write_event(event)
    pending_event = dict(event, id=uid(), cost=234)
    pending = await redis.xadd("tollgate:events", {"event": json.dumps(pending_event)})
    await prune_committed(repo, redis)
    assert not await redis.xrange("tollgate:events", min=committed, max=committed)
    assert await redis.xrange("tollgate:events", min=pending, max=pending)
    await reconcile(repo, app.state.fast)
    key = f"default:{event['customer_id']}:{event['created_at'][:7]}"
    assert await app.state.fast.spend(key) == 357
    await run_worker(repo, app.state.fast, once=True)
    assert not await redis.xrange("tollgate:events", min=pending, max=pending)
    assert await repo.spend("default", event["customer_id"], event["created_at"][:7]) == 357


async def test_postgres_snapshot_survives_concurrent_commit_and_stream_deletion(integration_app, monkeypatch):
    from tollgate.db import now, uid

    app = integration_app
    repo, redis = app.state.repo, app.state.fast.redis
    event = (await repo.logs())[0].copy()
    event.update(id=uid(), created_at=now(), customer_id="snapshot-" + uuid.uuid4().hex, cost=321)
    delivery = await redis.xadd("tollgate:events", {"event": json.dumps(event)})
    original = repo.committed_events
    raced = False

    async def commit_after_totals(events, session=None):
        nonlocal raced
        if session is not None and not raced:
            raced = True
            # Another worker commits after the repeatable-read totals query,
            # then deletes the delivery before the identity lookup completes.
            await repo.write_event(event)
            await redis.xdel("tollgate:events", delivery)
        return await original(events, session)

    monkeypatch.setattr(repo, "committed_events", commit_after_totals)
    assert await reconcile(repo, app.state.fast)
    key = f"default:{event['customer_id']}:{event['created_at'][:7]}"
    assert raced and await app.state.fast.spend(key) == 321
    assert await repo.spend("default", event["customer_id"], event["created_at"][:7]) == 321


async def test_committed_delivery_survives_worker_crash_before_ack(integration_app):
    from tollgate.db import now, uid

    app = integration_app
    repo, redis = app.state.repo, app.state.fast.redis
    await run_worker(repo, app.state.fast, once=True)
    event = (await repo.logs())[0].copy()
    event.update(id=uid(), created_at=now(), customer_id="replay-" + uuid.uuid4().hex, cost=456)
    delivery = await redis.xadd("tollgate:events", {"event": json.dumps(event)})
    await redis.xreadgroup("ledger", "crashed-worker", {"tollgate:events": ">"}, count=500)
    await repo.write_event(event)  # process dies before XACK/XDEL
    assert await redis.xrange("tollgate:events", min=delivery, max=delivery)
    await run_worker(repo, app.state.fast, once=True)
    assert not await redis.xrange("tollgate:events", min=delivery, max=delivery)
    assert not await redis.xpending_range("tollgate:events", "ledger", delivery, delivery, 1)
    rows = await repo.logs(customer=event["customer_id"])
    assert len(rows) == 1 and rows[0]["cost"] == 456
    daily = [row for row in await repo.daily("default") if row["customer_id"] == event["customer_id"]]
    assert len(daily) == 1 and daily[0]["requests"] == 1 and daily[0]["cost"] == 456


async def test_unknown_attempt_and_success_settle_durably_in_redis_postgres(integration_app):
    from datetime import UTC, datetime

    from tollgate.schemas import ChatRequest

    app = integration_app
    original = app.state.pipeline.providers.chat
    calls = 0

    async def timeout_once(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError()
        return await original(*args)

    app.state.pipeline.providers.chat = timeout_once
    customer = "uncertain-" + uuid.uuid4().hex
    response = await app.state.pipeline.execute(
        ChatRequest(model="smart", messages=[{"role": "user", "content": "Synthetic probe"}]).model_dump(
            exclude_none=True
        ),
        "default",
        customer,
    )
    assert response.status_code == 200 and calls == 2
    key = f"default:{customer}:{datetime.now(UTC).strftime('%Y-%m')}"
    before = await app.state.fast.spend(key)
    assert before > 0 and await app.state.fast.reserved(key) == 0
    await run_worker(app.state.repo, app.state.fast, once=True)
    event = (await app.state.repo.logs(customer=customer))[0]
    assert event["cost"] == before and 0 < event["uncertain_cost"] < before
    assert event["cost_basis"] == "conservative"
    assert await reconcile(app.state.repo, app.state.fast)
    assert await app.state.fast.spend(key) == before


async def test_recovery_retry_fences_even_existing_event_and_clears_after_reconcile(integration_app):
    from tollgate.db import now, uid

    app = integration_app
    event = (await app.state.repo.logs())[0].copy()
    event.update(id=uid(), created_at=now(), customer_id="marker-" + uuid.uuid4().hex, cost=90)
    await app.state.repo.write_event(event)
    await app.state.repo.write_event(event, recovery=True)
    await app.state.repo.write_event(event, recovery=True)
    assert await app.state.repo.recovery_pending("default")
    assert len(await app.state.repo.recovery_records()) == 1
    key = f"default:{event['customer_id']}:{event['created_at'][:7]}"
    await app.state.fast.initialize(key, 0)
    await app.state.fast.reserve(key, "still-running", 10000, [], [100])
    assert await reconcile(app.state.repo, app.state.fast)
    assert not await app.state.repo.recovery_pending("default")
    assert await app.state.fast.spend(key) == 90 and await app.state.fast.reserved(key) == 100


async def test_expired_reconciliation_cannot_overwrite_or_delete_successor_lock(integration_app, monkeypatch):
    app = integration_app
    redis = app.state.fast.redis
    key = "expired-lease:" + uuid.uuid4().hex
    await app.state.fast.initialize(key, 999)
    await app.state.fast.reserve(key, "active", 10000, [], [100])
    original = app.state.repo.ledger_snapshot

    async def expired(*args):
        snapshot = await original(*args)
        await redis.set("tollgate:reconcile-lock", "successor", ex=30)
        return snapshot

    monkeypatch.setattr(app.state.repo, "ledger_snapshot", expired)
    try:
        assert await reconcile(app.state.repo, app.state.fast) is False
        assert await redis.get("tollgate:reconcile-lock") == "successor"
        assert await app.state.fast.spend(key) == 999 and await app.state.fast.reserved(key) == 100
    finally:
        await redis.delete("tollgate:reconcile-lock")
