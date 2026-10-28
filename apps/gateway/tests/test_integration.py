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
