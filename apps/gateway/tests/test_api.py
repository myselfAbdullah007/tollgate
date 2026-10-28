import json

import pytest
from tollgate.providers import ProviderError

BODY = {
    "model": "smart",
    "messages": [{"role": "user", "content": "Email ali@example.com about a refund"}],
    "temperature": 0,
}


async def test_auth_ops_models(client, auth):
    assert (await client.get("/healthz")).status_code == 200
    assert (await client.get("/readyz")).status_code == 200
    assert (await client.get("/metrics")).status_code == 200
    assert (await client.post("/v1/chat/completions", json=BODY)).status_code == 401
    assert (await client.get("/admin/v1/tenants")).status_code == 401
    r = await client.get("/v1/models", headers=auth)
    assert "smart" in [m["id"] for m in r.json()["data"]]


async def test_redaction_cache_and_no_pii_persisted(client, app, auth):
    r = await client.post("/v1/chat/completions", json=BODY, headers=auth)
    assert r.status_code == 200, r.text
    assert "ali@example.com" in r.json()["choices"][0]["message"]["content"]
    assert r.headers["x-tollgate-cache"] == "MISS"
    next_body = dict(BODY, messages=[{"role": "user", "content": "Email bob@example.com about a refund"}])
    r = await client.post("/v1/chat/completions", json=next_body, headers=auth)
    assert r.headers["x-tollgate-cache"] == "HIT"
    assert "bob@example.com" in r.text and "ali@example.com" not in r.text
    logs = await app.state.repo.logs()
    assert "ali@example.com" not in json.dumps(logs) and "bob@example.com" not in json.dumps(logs)
    assert "ali@example.com" not in json.dumps(app.state.fast.cache)
    assert r.json()["usage"]["total_tokens"] == 0


@pytest.mark.parametrize("stream", [False, True])
async def test_streaming_and_fallback(client, app, auth, stream):
    alias = await app.state.repo.find("alias", "smart")
    alias["tiers"][0] = ["mock/outage", "mock/backup"]
    await app.state.repo.put("alias", "smart", alias, id=alias["id"])
    r = await client.post("/v1/chat/completions", json=dict(BODY, stream=stream), headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["x-tollgate-model-served"] == "mock/backup"
    if stream:
        chunks = [
            json.loads(line[6:])
            for line in r.text.splitlines()
            if line.startswith("data: ") and line != "data: [DONE]"
        ]
        text = "".join(
            c.get("choices", [{}])[0].get("delta", {}).get("content", "") for c in chunks if c["choices"]
        )
        assert "ali@example.com" in text and "[EMAIL" not in text
        assert r.text.endswith("data: [DONE]\n\n")
    assert (await app.state.repo.logs())[0]["fallback_count"] == 1


async def test_stream_failure_never_falls_back_after_first_byte(client, app, auth):
    calls = []

    async def fail(target, request, tenant):
        calls.append(target)
        yield {"delta": {"content": "start"}}
        raise ProviderError()

    app.state.pipeline.providers.stream = fail
    r = await client.post("/v1/chat/completions", json=dict(BODY, stream=True), headers=auth)
    assert len(calls) == 1
    assert "Provider stream interrupted" in r.text
    logs = await app.state.repo.logs()
    assert logs[0]["status"] == "error" and logs[0]["cost"] > 0


async def test_degradation_exhaustion_and_card_block(client, app, auth):
    customer = await app.state.pipeline.customer("default", "test_customer")
    await app.state.repo.put(
        "customer", customer["name"], dict(customer, budget_override=100000), id=customer["id"]
    )
    from datetime import UTC, datetime

    key = "default:test_customer:" + datetime.now(UTC).strftime("%Y-%m")
    app.state.fast.spends[key] = 96000
    r = await client.post("/v1/chat/completions", json=dict(BODY, max_tokens=10), headers=auth)
    assert r.status_code == 200 and r.headers["x-tollgate-tier"] == "2"
    app.state.fast.spends[key] = 100000
    assert (await client.post("/v1/chat/completions", json=BODY, headers=auth)).status_code == 402
    blocked = dict(BODY, messages=[{"role": "user", "content": "Pay 4111 1111 1111 1111"}])
    assert (await client.post("/v1/chat/completions", json=blocked, headers=auth)).status_code == 422


async def test_admin_crud_revocation_and_csrf(admin):
    c = admin
    r = await c.post("/admin/v1/tenants/default/keys", json={"name": "New key"})
    assert r.status_code == 200, r.text
    raw, id = r.json()["key"], r.json()["id"]
    assert "key_hash" not in r.json()
    assert raw not in (await c.get("/admin/v1/tenants/default/keys")).text
    assert (await c.get("/v1/models", headers={"Authorization": "Bearer " + raw})).status_code == 200
    assert (await c.delete("/admin/v1/tenants/default/keys/" + id)).status_code == 200
    assert (await c.get("/v1/models", headers={"Authorization": "Bearer " + raw})).status_code == 401
    r = await c.post(
        "/admin/v1/tenants/default/customers", json={"name": "new", "display_name": "New Co", "plan": "Pro"}
    )
    assert r.status_code == 200
    r = await c.post("/admin/v1/pii/preview", json={"text": "ali@example.com"})
    assert r.json()["redacted"] == "[EMAIL_1]"
    r = await c.post(
        "/admin/v1/pii/preview", json={"text": "ali@example.com"}, headers={"Origin": "https://evil.example"}
    )
    assert r.status_code == 403
    assert (await c.get("/admin/v1/tenants/default/usage")).json()["requests"] > 0
    assert (await c.get("/admin/v1/tenants/default/logs?q=cus_acme")).json()["total"] == 28


async def test_provider_secrets_encrypted_and_not_returned(admin, app):
    secret = "sk-pretend-secret-provider"
    r = await admin.put("/admin/v1/providers", json={"provider": "openai", "key": secret})
    assert r.status_code == 200
    row = await app.state.repo.find("provider", "openai")
    assert secret not in json.dumps(row)
    assert secret not in (await admin.get("/admin/v1/providers")).text


async def test_validation_missing_customer_and_quality_locked(client, app, auth):
    assert (
        await client.post("/v1/chat/completions", json=BODY, headers={"Authorization": auth["Authorization"]})
    ).status_code == 400
    assert (
        await client.post("/v1/chat/completions", json=dict(BODY, max_tokens=-1), headers=auth)
    ).status_code == 422
    assert (
        await client.post("/v1/chat/completions", json=dict(BODY, model="does-not-exist"), headers=auth)
    ).status_code == 400


async def test_stream_cache_uses_current_vault(client, auth):
    r = await client.post("/v1/chat/completions", json=dict(BODY, stream=True), headers=auth)
    assert r.status_code == 200
    body = dict(
        BODY, stream=True, messages=[{"role": "user", "content": "Email bob@example.com about a refund"}]
    )
    r = await client.post("/v1/chat/completions", json=body, headers=auth)
    assert r.headers["x-tollgate-cache"] == "HIT"
    assert "bob@example.com" in r.text and "ali@example.com" not in r.text


async def test_rejected_requests_logged_without_prompt(client, app, auth):
    body = dict(BODY, messages=[{"role": "user", "content": "Pay 4111 1111 1111 1111"}])
    r = await client.post("/v1/chat/completions", json=body, headers=auth)
    assert r.status_code == 422
    row = (await app.state.repo.logs(customer="test_customer"))[0]
    assert row["error_code"] == "pii_blocked" and row["cost"] == 0
    assert "4111" not in json.dumps(row)


async def test_tenant_cache_and_key_isolation(admin, app, auth):
    await admin.post("/admin/v1/tenants", json={"name": "other", "display_name": "Other"})
    key = (await admin.post("/admin/v1/tenants/other/keys", json={"name": "other-key"})).json()["key"]
    first = await admin.post("/v1/chat/completions", json=BODY, headers=auth)
    second = await admin.post(
        "/v1/chat/completions",
        json=BODY,
        headers={"Authorization": "Bearer " + key, "X-Tollgate-Customer": "test_customer"},
    )
    assert first.status_code == second.status_code == 200
    assert second.headers["x-tollgate-cache"] == "MISS"
    rows = await app.state.repo.logs("other")
    assert len(rows) == 1 and rows[0]["tenant_id"] == "other"


async def test_no_cache_when_privacy_off(client, app, auth):
    plan = await app.state.repo.find("plan", "Pro")
    plan["pii_mode"] = "off"
    await app.state.repo.put("plan", "Pro", plan, id=plan["id"])
    r = await client.post("/v1/chat/completions", json=BODY, headers=auth)
    assert r.status_code == 200
    assert not app.state.fast.cache


async def test_malformed_tool_and_content_validation(client, auth):
    for content in [[None], [{"type": "image_url", "image_url": {}}]]:
        response = await client.post(
            "/v1/chat/completions",
            json=dict(BODY, messages=[{"role": "user", "content": content}]),
            headers=auth,
        )
        assert response.status_code == 422
    response = await client.post(
        "/v1/chat/completions",
        json=dict(BODY, tools=[{"type": "function", "function": {"name": "x"}}]),
        headers=auth,
    )
    assert response.status_code == 422


async def test_concurrent_demo_requests_preserve_rollup(client, app, auth):
    import asyncio

    headers = dict(auth, **{"X-Tollgate-Customer": "concurrent_customer"})
    responses = await asyncio.gather(
        *(
            client.post("/v1/chat/completions", json=dict(BODY, temperature=1), headers=headers)
            for _ in range(20)
        )
    )
    assert all(r.status_code == 200 for r in responses)
    rows = await app.state.repo.logs(customer="concurrent_customer")
    assert len(rows) == 20
    daily = [r for r in await app.state.repo.daily("default") if r["customer_id"] == "concurrent_customer"]
    assert sum(r["requests"] for r in daily) == 20
    assert sum(r["cost"] for r in daily) == sum(r["cost"] for r in rows)
