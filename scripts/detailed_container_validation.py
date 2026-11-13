"""Mock-only destructive exercises for a disposable validation stack.

Requires validation-* Compose services on tollgate_validation, fresh demo stores,
ports 3188/8188 and local readiness-validation images. Never use production data.
Creates tollgate_restored and tollgate_validation_restore_redis; leaves the source
gateway/worker stopped for inspection. The caller owns setup and cleanup.
"""

import argparse
import asyncio
import datetime
import json
import pathlib
import subprocess
import time

import httpx
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--work-dir", type=pathlib.Path, required=True)
parser.add_argument("--output-dir", type=pathlib.Path, required=True)
options = parser.parse_args()
ROOT = options.work_dir.resolve()
OUT = options.output_dir.resolve()
OUT.mkdir(parents=True, exist_ok=True)
config = yaml.safe_load((ROOT / "compose.yml").read_text())
assert config["name"] == "tollgate"
assert all(name.startswith("validation-") for name in config["services"])
for name in ("validation-gateway", "validation-worker"):
    env = config["services"][name]["environment"]
    assert str(env["TOLLGATE_DEMO"]).lower() == "true"
    assert env["TOLLGATE_DATABASE_URL"].endswith("@postgres:5432/tollgate")
    assert env["TOLLGATE_REDIS_URL"] == "redis://redis:6379/0"
    assert all(
        not env.get(key)
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
    )
COMPOSE = ["docker", "compose", "-f", str(ROOT / "compose.yml")]
results = {}


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs).stdout


async def command(*args):
    return await asyncio.to_thread(run, *args)


async def compose(*args):
    return await command(*COMPOSE, *args)


def sql(query):
    return (
        run(
            "docker",
            "exec",
            "tollgate-validation-postgres-1",
            "psql",
            "-U",
            "tollgate",
            "-d",
            "tollgate",
            "-Atc",
            query,
        )
        .decode()
        .strip()
    )


def redis(*args):
    return (
        run("docker", "exec", "tollgate-validation-redis-1", "redis-cli", *args)
        .decode()
        .strip()
    )


async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8188", timeout=30) as c:

        async def post(path, body):
            r = await c.post(path, json=body)
            r.raise_for_status()
            return r.json()

        await post(
            "/admin/v1/auth/login",
            {"email": "admin@tollgate.local", "password": "tollgate-demo-2026"},
        )
        c.headers["X-Tollgate-Admin"] = "1"
        await post(
            "/admin/v1/tenants/default/plans",
            {"name": "detailed-load", "monthly_budget": 1000000000, "rpm": 100000},
        )
        await post(
            "/admin/v1/tenants/default/customers",
            {
                "name": "detailed-load",
                "display_name": "Synthetic load fixture",
                "plan": "detailed-load",
            },
        )
        await post(
            "/admin/v1/tenants/default/aliases",
            {"name": "detailed-load", "tiers": [["mock/outage", "mock/backup"]]},
        )
        headers = {
            "Authorization": "Bearer tg_live_demo_tollgate_local_only",
            "X-Tollgate-Customer": "detailed-load",
        }
        latencies = []
        statuses = {}
        failures = []

        async def request(i):
            start = time.monotonic()
            streaming = i % 4 == 0
            body = {
                "model": "detailed-load",
                "messages": [
                    {
                        "role": "user",
                        "content": f"Case {i}: contact synthetic@example.com",
                    }
                ],
                "stream": streaming,
                "temperature": 0 if i % 4 == 1 else 1,
            }
            if streaming:
                body["stream_options"] = {"include_usage": True}
            r = await c.post("/v1/chat/completions", headers=headers, json=body)
            latencies.append((time.monotonic() - start) * 1000)
            statuses[str(r.status_code)] = statuses.get(str(r.status_code), 0) + 1
            if (
                r.status_code != 200
                or "synthetic@example.com" not in r.text
                or "[EMAIL_" in r.text
                or (streaming and "[DONE]" not in r.text)
            ):
                failures.append({"case": i, "status": r.status_code})

        start = time.monotonic()
        semaphore = asyncio.Semaphore(20)

        async def bounded(i):
            async with semaphore:
                await request(i)

        await asyncio.gather(*(bounded(i) for i in range(200)))
        burst = time.monotonic() - start
        start = time.monotonic()
        for i in range(240):
            await request(200 + i)
            await asyncio.sleep(max(0, start + (i + 1) * 0.5 - time.monotonic()))
        soak = time.monotonic() - start
        ordered = sorted(latencies)
        results["load"] = {
            "requests": 440,
            "burst_requests": 200,
            "burst_concurrency": 20,
            "burst_seconds": burst,
            "soak_requests": 240,
            "soak_seconds": soak,
            "target_soak_rps": 2,
            "statuses": dict(statuses),
            "failures": list(failures),
            "latency_ms": {
                p: ordered[int((len(ordered) - 1) * q)]
                for p, q in [("p50", 0.5), ("p95", 0.95), ("p99", 0.99)]
            },
        }
        assert not failures, results["load"]
        for _ in range(100):
            n = int(
                await asyncio.to_thread(
                    sql,
                    "select count(*) from request_logs where customer_id='detailed-load'",
                )
            )
            if n == 440:
                break
            await asyncio.sleep(0.2)
        assert n == 440, n
        results["ledger_after_load"] = n
        await compose("stop", "validation-worker")
        await request(440)
        pending = int(await asyncio.to_thread(redis, "XLEN", "tollgate:events"))
        assert pending >= 1
        await compose("start", "validation-worker")
        for _ in range(100):
            n = int(
                await asyncio.to_thread(
                    sql,
                    "select count(*) from request_logs where customer_id='detailed-load'",
                )
            )
            if n == 441:
                break
            await asyncio.sleep(0.2)
        assert (
            n == 441
            and int(await asyncio.to_thread(redis, "XLEN", "tollgate:events")) == 0
        )
        results["worker_restart"] = {
            "pending_while_stopped": pending,
            "ledger_after_restart": n,
        }
        for service in ["validation-postgres", "validation-redis"]:
            await compose("stop", service)
            r = await c.get("/readyz")
            assert r.status_code == 503, (service, r.status_code)
            await compose("start", service)
            for _ in range(100):
                r = await c.get("/readyz")
                if r.status_code == 200:
                    break
                await asyncio.sleep(0.2)
            assert r.status_code == 200
            results[service + "_outage"] = {"during": 503, "recovered": 200}
        # Quiesce writes and capture a coordinated SQL + Redis snapshot with one undelivered event.
        await compose("stop", "validation-worker")
        await request(441)
        await compose("stop", "validation-gateway")
        key = "default:detailed-load:" + datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m"
        )
        await asyncio.to_thread(
            redis, "HSET", "reserved:" + key, "backup-inflight", "123"
        )
        await asyncio.to_thread(
            redis, "ZADD", "deadlines:" + key, str(time.time() + 180), "backup-inflight"
        )
        expected_cost = int(await asyncio.to_thread(redis, "GET", "spend:" + key))
        expected_pending = int(
            await asyncio.to_thread(redis, "XLEN", "tollgate:events")
        )
        assert expected_pending == 1, expected_pending
        start = time.monotonic()
        dump = await command(
            "docker",
            "exec",
            "tollgate-validation-postgres-1",
            "pg_dump",
            "-U",
            "tollgate",
            "-Fc",
            "tollgate",
        )
        (ROOT / "backup.dump").write_bytes(dump)
        await asyncio.to_thread(redis, "SAVE")
        await command(
            "docker",
            "cp",
            "tollgate-validation-redis-1:/data/dump.rdb",
            str(ROOT / "dump.rdb"),
        )
        backup_seconds = time.monotonic() - start
        await command(
            "docker",
            "exec",
            "tollgate-validation-postgres-1",
            "createdb",
            "-U",
            "tollgate",
            "tollgate_restored",
        )
        await asyncio.to_thread(
            run,
            "docker",
            "exec",
            "-i",
            "tollgate-validation-postgres-1",
            "pg_restore",
            "-U",
            "tollgate",
            "-d",
            "tollgate_restored",
            input=dump,
        )
        await command("docker", "volume", "create", "tollgate_validation_restore_redis")
        await command(
            "docker",
            "run",
            "--rm",
            "-v",
            "tollgate_validation_restore_redis:/dest",
            "-v",
            str(ROOT) + ":/backup:ro",
            "--entrypoint",
            "sh",
            "redis:7.4.8-alpine",
            "-c",
            "cp /backup/dump.rdb /dest/dump.rdb && chown redis:redis /dest/dump.rdb",
        )
        await command(
            "docker",
            "run",
            "-d",
            "--name",
            "tollgate-validation-restore-redis",
            "--network",
            "tollgate_validation",
            "--network-alias",
            "restore-redis",
            "--label",
            "com.docker.compose.project=tollgate",
            "-v",
            "tollgate_validation_restore_redis:/data",
            "redis:7.4.8-alpine",
            "redis-server",
            "--appendonly",
            "no",
        )
        verify = """
import asyncio,json
from sqlalchemy import text
from tollgate.db import Database
from tollgate.repository import Repository
from tollgate.fastpath import FastPath
from tollgate.worker import run_worker
async def main():
 db=Database('postgresql+asyncpg://tollgate:tollgate-local-only@postgres:5432/tollgate_restored')
 fast=FastPath('redis://restore-redis:6379/0');repo=Repository(db)
 key=KEY
 assert await fast.reserved(key)==123
 assert await fast.redis.xlen('tollgate:events')==1
 await run_worker(repo,fast,once=True)
 async with db.session() as s:
  row=(await s.execute(text("select count(*),sum(cost) from request_logs where customer_id='detailed-load'"))).one()
 assert row[0]==442,row
 assert row[1]==EXPECTED_COST,(row,EXPECTED_COST)
 assert await fast.spend(key)==EXPECTED_COST
 assert await fast.reserved(key)==123
 assert await fast.redis.xlen('tollgate:events')==0
 print(json.dumps({'restored_logs':row[0],'restored_cost_micro_usd':int(row[1]),'inflight_preserved':123,'pending_delivered':1}))
 await fast.redis.aclose();await db.engine.dispose()
asyncio.run(main())
""".replace("KEY", repr(key)).replace("EXPECTED_COST", str(expected_cost))
        start = time.monotonic()
        output = await command(
            "docker",
            "run",
            "--rm",
            "--network",
            "tollgate_validation",
            "--entrypoint",
            "python",
            "tollgate:readiness-validation",
            "-c",
            verify,
        )
        results["backup_restore"] = {
            "backup_seconds": backup_seconds,
            "verification_seconds": time.monotonic() - start,
            "sql_bytes": len(dump),
            "redis_bytes": (ROOT / "dump.rdb").stat().st_size,
            **json.loads(output),
        }
        print(json.dumps(results, indent=2))


try:
    asyncio.run(main())
finally:
    (OUT / "container-exercises.json").write_text(json.dumps(results, indent=2) + "\n")
