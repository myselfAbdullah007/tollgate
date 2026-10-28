"""Controlled Docker smoke with alphabetic routing identifiers; only mock targets."""

import asyncio
import json
import uuid
from pathlib import Path

import httpx


async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8187", timeout=20) as client:
        ready = (await client.get("/readyz")).json()
        response = await client.post(
            "/admin/v1/auth/login", json={"email": "admin@tollgate.local", "password": "tollgate-demo-2026"}
        )
        response.raise_for_status()
        client.headers["X-Tollgate-Admin"] = "1"
        # Map UUID nibbles to letters so aliases cannot accidentally look like card/phone values.
        suffix = "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex)
        alias = "audit-" + suffix
        response = await client.post(
            "/admin/v1/tenants/default/aliases",
            json={
                "name": alias,
                "allow_degrade": True,
                "tiers": [["mock/outage", "mock/backup"], ["mock/balanced"], ["mock/economy"]],
            },
        )
        response.raise_for_status()
        alias_id = response.json()["id"]
        result = {"readiness": ready}
        try:
            headers = {
                "Authorization": "Bearer tg_live_demo_tollgate_local_only",
                "X-Tollgate-Customer": "audit-" + suffix,
            }
            body = {
                "model": alias,
                "stream": True,
                "messages": [{"role": "user", "content": "Email fixture@example.com"}],
            }
            response = await client.post("/v1/chat/completions", headers=headers, json=body)
            response.raise_for_status()
            result.update(
                stream_status=response.status_code,
                fallback_model=response.headers["x-tollgate-model-served"],
                pii_restored="fixture@example.com" in response.text,
                done="data: [DONE]" in response.text,
            )
            for _ in range(40):
                logs = (
                    await client.get("/admin/v1/tenants/default/logs", params={"customer": "audit-" + suffix})
                ).json()["items"]
                if logs:
                    break
                await asyncio.sleep(0.1)
            result["worker_delivery"] = len(logs) == 1
            result["pii_absent_from_ledger"] = "fixture@example.com" not in json.dumps(logs)
            result["fallback_count"] = logs[0]["fallback_count"] if logs else None
            headers["X-Tollgate-Customer"] = "cus_orbit"
            degraded = await client.post(
                "/v1/chat/completions", headers=headers, json=dict(body, stream=False, max_tokens=32)
            )
            result.update(
                degradation_status=degraded.status_code,
                degradation_tier=degraded.headers.get("x-tollgate-tier"),
            )
            assert result["fallback_model"] == "mock/backup" and result["pii_restored"] and result["done"]
            assert result["worker_delivery"] and result["pii_absent_from_ledger"]
            assert degraded.status_code == 200 and result["degradation_tier"] == "2"
        finally:
            await client.delete("/admin/v1/tenants/default/aliases/" + alias_id)
        path = Path("docs/audits/2026-10-28/deployment-probes.json")
        path.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


asyncio.run(main())
