"""Exercise pull-only deployment against a fresh database; use mock targets only."""

import asyncio
import json
import os
import uuid

import httpx


async def main():
    base = os.getenv("TOLLGATE_SMOKE_URL", "http://localhost:3187")
    # Use the dashboard proxy too, proving its baked-in gateway address works.
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        response = await client.get("/login")
        response.raise_for_status()
        response = await client.get("/api/readyz")
        response.raise_for_status()
        ready = response.json()
        assert ready["storage"] == "postgres" and ready["fast_path"] == "redis"
        response = await client.get("/api/healthz")
        response.raise_for_status()
        assert response.json()["demo"] is False
        response = await client.post("/api/admin/v1/auth/login", json={
            "email": os.environ["TOLLGATE_ADMIN_EMAIL"],
            "password": os.environ["TOLLGATE_ADMIN_PASSWORD"],
        })
        response.raise_for_status()
        client.headers["X-Tollgate-Admin"] = "1"
        response = await client.get("/api/admin/v1/tenants/default/keys")
        response.raise_for_status()
        assert response.json() == [], "Use a fresh non-demo deployment"
        suffix = "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex)
        response = await client.post("/api/admin/v1/tenants/default/keys", json={"name": "smoke-" + suffix})
        response.raise_for_status()
        key = response.json()
        alias_id = None
        try:
            response = await client.post("/api/admin/v1/tenants/default/aliases", json={
                "name": "smoke-" + suffix,
                "allow_degrade": True,
                "tiers": [["mock/outage", "mock/backup"], ["mock/balanced"]],
            })
            response.raise_for_status()
            alias_id = response.json()["id"]
            response = await client.post("/api/v1/chat/completions", headers={
                "Authorization": "Bearer " + key["key"],
                "X-Tollgate-Customer": "smoke-" + suffix,
            }, json={
                "model": "smoke-" + suffix,
                "stream": True,
                "messages": [{"role": "user", "content": "Email image-smoke@example.com"}],
            })
            response.raise_for_status()
            assert response.headers["x-tollgate-model-served"] == "mock/backup"
            assert "image-smoke@example.com" in response.text and "[DONE]" in response.text
            assert "[EMAIL_" not in response.text
            rows = []
            for _ in range(50):
                response = await client.get("/api/admin/v1/tenants/default/logs", params={"customer": "smoke-" + suffix})
                response.raise_for_status()
                rows = response.json()["items"]
                if rows:
                    break
                await asyncio.sleep(0.2)
            assert len(rows) == 1 and rows[0]["fallback_count"] == 1
            assert "image-smoke@example.com" not in json.dumps(rows)
            print("PASS: non-demo image deployment, dashboard proxy, external stores, key creation,")
            print("      mock streaming/fallback/restoration, durable worker, metadata-only ledger")
        finally:
            if alias_id:
                response = await client.delete("/api/admin/v1/tenants/default/aliases/" + alias_id)
                response.raise_for_status()
            response = await client.delete("/api/admin/v1/tenants/default/keys/" + key["id"])
            response.raise_for_status()


if __name__ == "__main__":
    asyncio.run(main())
