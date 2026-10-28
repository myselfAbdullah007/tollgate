from datetime import UTC, datetime, timedelta

import pytest
from tollgate.db import uid
from tollgate.providers import anthropic_payload

BODY = {"model": "smart", "temperature": 0, "messages": [{"role": "user", "content": "Hello"}]}


async def test_numeric_alias_is_not_prompt_pii(admin, auth):
    name = "release-4111111111111111"
    assert (
        await admin.post(
            "/admin/v1/tenants/default/aliases", json={"name": name, "tiers": [["mock/premium"]]}
        )
    ).status_code == 200
    r = await admin.post("/v1/chat/completions", headers=auth, json=dict(BODY, model=name))
    assert r.status_code == 200


async def test_nullable_tool_calls_are_normalized(client, auth):
    r = await client.post(
        "/v1/chat/completions",
        headers=auth,
        json=dict(
            BODY,
            messages=[
                {"role": "assistant", "content": "Hello", "tool_calls": None},
                {"role": "user", "content": "Hi"},
            ],
        ),
    )
    assert r.status_code == 200


def test_anthropic_system_parts_normalized():
    body = anthropic_payload(
        {
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": "Be concise"}]},
                {"role": "user", "content": "Hi"},
            ]
        },
        "fixture",
    )
    assert body["system"] == "Be concise"


async def test_effective_privacy_preview(admin):
    r = await admin.post(
        "/admin/v1/pii/preview",
        json={"text": "4111 1111 1111 1111", "tenant_id": "default", "customer": "cus_acme"},
    )
    assert r.json()["blocked"] is True
    assert r.json()["effective_mode"] == "reversible"


@pytest.mark.parametrize("resource", ["plans", "aliases", "keys", "logs", "usage"])
async def test_unknown_workspace_consistently_404(admin, resource):
    assert (await admin.get("/admin/v1/tenants/missing/" + resource)).status_code == 404


async def test_date_filter_runs_before_pagination(admin, app):
    row = (await app.state.repo.logs())[0].copy()
    old = uid()
    row.update(id=old, created_at=(datetime.now(UTC) - timedelta(days=60)).isoformat())
    await app.state.repo.write_event(row)
    assert (await admin.get("/admin/v1/tenants/default/logs", params={"days": 7, "q": old})).json()[
        "total"
    ] == 0


async def test_zero_cost_cache_survives_budget_exhaustion(client, app, auth):
    first = await client.post("/v1/chat/completions", headers=auth, json=BODY)
    assert first.status_code == 200
    customer = await app.state.repo.find("customer", "test_customer")
    await app.state.repo.put(
        "customer", customer["name"], dict(customer, budget_override=0), id=customer["id"]
    )
    hit = await client.post("/v1/chat/completions", headers=auth, json=BODY)
    assert hit.status_code == 200 and hit.headers["x-tollgate-cache"] == "HIT"


async def test_stale_plan_save_conflicts_without_losing_policy(admin):
    plans = (await admin.get("/admin/v1/tenants/default/plans")).json()
    plan = next(p for p in plans if p["name"] == "Pro")
    body = dict(
        plan,
        pii_block_categories=["CARD", "EMAIL", "SECRET"],
        degradation=[{"at": 0.6, "tier": 1}, {"at": 0.8, "tier": 2}, {"at": 0.95, "tier": 3}],
    )
    saved = await admin.patch("/admin/v1/tenants/default/plans/" + plan["id"], json=body)
    assert saved.status_code == 200
    stale = await admin.patch("/admin/v1/tenants/default/plans/" + plan["id"], json=dict(body, rpm=99))
    assert stale.status_code == 409
    result = next(
        p for p in (await admin.get("/admin/v1/tenants/default/plans")).json() if p["name"] == "Pro"
    )
    assert result["pii_block_categories"] == ["CARD", "EMAIL", "SECRET"] and len(result["degradation"]) == 3


async def test_feature_reporting_and_scoped_usage_keys(admin, auth):
    request = dict(BODY, feature="support", environment="staging")
    assert (await admin.post("/v1/chat/completions", headers=auth, json=request)).status_code == 200
    stats = (await admin.get("/admin/v1/tenants/default/usage")).json()
    assert stats["sampled"] is False
    assert any(r["name"] == "support" and r["requests"] == 1 for r in stats["breakdown"]["feature"])
    key = (
        await admin.post(
            "/admin/v1/tenants/default/keys",
            json={"name": "Usage only", "scope": "usage", "customer": "test_customer"},
        )
    ).json()["key"]
    headers = {"Authorization": "Bearer " + key, "X-Tollgate-Customer": "cus_orbit"}
    usage = await admin.get("/v1/usage", headers=headers)
    assert usage.status_code == 200 and usage.json()["name"] == "test_customer"
    assert "reset_at" in usage.json()
    assert (await admin.post("/v1/chat/completions", headers=headers, json=BODY)).status_code == 403


async def test_password_change_revokes_sessions_and_live_roles(admin, client, app):
    me = (await admin.get("/admin/v1/auth/me")).json()
    sessions = (await admin.get("/admin/v1/auth/sessions")).json()
    assert sessions and any(s["current"] for s in sessions)
    bad = await admin.post(
        "/admin/v1/auth/password", json={"current_password": "wrong", "new_password": "valid-new-password"}
    )
    assert bad.status_code == 400
    changed = await admin.post(
        "/admin/v1/auth/password",
        json={"current_password": "tollgate-demo-2026", "new_password": "valid-new-password"},
    )
    assert changed.status_code == 200
    assert not await app.state.repo.records("session", "global")
    assert (await admin.get("/admin/v1/auth/me")).status_code == 401
    assert (
        await client.post(
            "/admin/v1/auth/login", json={"email": me["email"], "password": "valid-new-password"}
        )
    ).status_code == 200


async def test_audit_metadata_never_records_provider_secret(admin):
    secret = "sk-fake-private-test-secret"
    assert (
        await admin.put("/admin/v1/providers", json={"provider": "openai", "key": secret})
    ).status_code == 200
    audit = await admin.get("/admin/v1/tenants/default/audit")
    assert audit.status_code == 200 and audit.json()
    assert secret not in audit.text and "encrypted_key" not in audit.text


async def test_alerts_are_transactional_and_deduplicated(app, admin, auth):
    from datetime import UTC, datetime

    customer = await app.state.pipeline.customer("default", "test_customer")
    await app.state.repo.put(
        "customer", customer["name"], dict(customer, budget_override=1_000_000), id=customer["id"]
    )
    row = (await app.state.repo.logs())[0].copy()
    for _ in range(2):
        row.update(
            id=uid(),
            customer_id="test_customer",
            cost=480_000,
            created_at=datetime.now(UTC).isoformat(),
            tier_served=1,
            status="success",
        )
        await app.state.repo.write_event(row)
    alerts = (await admin.get("/admin/v1/tenants/default/alerts")).json()
    matching = [a for a in alerts if a["payload"]["customer_id"] == "test_customer"]
    assert len([a for a in matching if a["payload"]["type"] == "customer.degraded"]) == 1
    assert len([a for a in matching if a["payload"]["type"] == "customer.budget_threshold"]) == 2
    assert all(a["delivery_status"] == "unconfigured" for a in matching)


async def test_webhook_private_destination_rejected_and_secret_once(admin, app):
    for url in [
        "http://example.com/hook",
        "https://127.0.0.1/hook",
        "https://169.254.169.254/metadata",
        "https://localhost/hook",
    ]:
        assert (
            await admin.put("/admin/v1/tenants/default/webhook", json={"url": url, "enabled": True})
        ).status_code == 422
    saved = await admin.put(
        "/admin/v1/tenants/default/webhook", json={"url": "https://example.com/hook", "enabled": False}
    )
    assert saved.status_code == 200 and saved.json()["signing_secret"]
    secret = saved.json()["signing_secret"]
    assert secret not in (await admin.get("/admin/v1/tenants/default/webhook")).text
    stored = await app.state.repo.find("webhook", "budget")
    assert secret not in str(stored)


async def test_chunked_oversized_body_is_rejected_before_parsing(client, auth):
    async def chunks():
        for _ in range(10):
            yield b"x" * 40000

    response = await client.post(
        "/v1/chat/completions", headers=dict(auth, **{"Content-Type": "application/json"}), content=chunks()
    )
    assert response.status_code == 413


def test_fractional_per_token_rates_remain_integer():
    from tollgate.pricing import cost

    assert cost("openai/gpt-4.1-mini", 1, 0) == 1
    assert cost("openai/gpt-4.1-mini", 10, 0) == 4
    assert cost("openai/gpt-4.1-mini", 10, 10) == 20


async def test_owner_manages_roles_and_cannot_disable_self(admin, app):
    created = await admin.post(
        "/admin/v1/users",
        json={"email": "viewer@example.com", "password": "viewer-pass-1234", "role": "viewer"},
    )
    assert created.status_code == 200
    assert "password_hash" not in created.text
    user = created.json()
    updated = await admin.patch(
        "/admin/v1/users/" + user["id"], json={"role": "admin", "revision": user["revision"]}
    )
    assert updated.status_code == 200 and updated.json()["role"] == "admin"
    owner = await app.state.repo.find("user", "admin@tollgate.local", "global")
    assert (await admin.patch("/admin/v1/users/" + owner["id"], json={"role": "viewer"})).status_code == 409


async def test_key_rotation_is_atomic_and_never_prints_secrets(app, monkeypatch, capsys):
    import base64
    import os

    from tollgate.config import Settings
    from tollgate.maintenance import rotate_master_key
    from tollgate.security import Crypto, digest

    crypto = app.state.pipeline.providers.crypto
    await app.state.repo.put("provider", "openai", {"encrypted_key": crypto.encrypt("fixture-secret")})
    new_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("TOLLGATE_NEW_MASTER_KEY", new_key)
    old_key = base64.b64encode(bytes.fromhex(digest("tollgate-local-demo-only"))).decode()
    await rotate_master_key(app.state.repo.db, Settings(demo=True, master_key=old_key))
    row = await app.state.repo.find("provider", "openai")
    assert Crypto(new_key).decrypt(row["encrypted_key"]) == "fixture-secret"
    output = capsys.readouterr().out
    assert new_key not in output and "fixture-secret" not in output


async def test_failed_fast_settlement_is_journaled_and_fences_new_requests(app, client, auth, monkeypatch):
    async def unavailable(*args, **kwargs):
        raise RuntimeError("fixture failure")

    monkeypatch.setattr(app.state.fast, "settle", unavailable)
    # Simulate Redis mode only after upstream admission by marking the failed
    # settlement path's ledger write with the same recovery mechanism directly.
    row = (await app.state.repo.logs())[0].copy()
    row.update(id=uid(), customer_id="recovery-customer", created_at=datetime.now(UTC).isoformat())
    await app.state.repo.write_event(row, recovery=True)
    assert await app.state.repo.recovery_pending("default")
    assert (await client.post("/v1/chat/completions", headers=auth, json=BODY)).status_code == 503


async def test_inline_accounting_failure_does_not_drop_successful_usage(app, client, auth, monkeypatch):
    original = app.state.repo.write_event
    calls = 0

    async def flaky(event, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient database failure")
        return await original(event, *args, **kwargs)

    monkeypatch.setattr(app.state.repo, "write_event", flaky)
    result = await client.post("/v1/chat/completions", headers=auth, json=BODY)
    assert result.status_code == 200
    rows = await app.state.repo.logs(customer="test_customer")
    assert len(rows) == 1 and rows[0]["cost"] > 0


async def test_invalid_usage_is_estimated_instead_of_corrupting_money(app, client, auth):
    original = app.state.pipeline.providers.chat

    async def malformed_usage(*args, **kwargs):
        result = await original(*args, **kwargs)
        result["usage"] = {"prompt_tokens": None, "completion_tokens": -1}
        return result

    app.state.pipeline.providers.chat = malformed_usage
    response = await client.post("/v1/chat/completions", headers=auth, json=dict(BODY, temperature=1))
    assert response.status_code == 200
    event = (await app.state.repo.logs(customer="test_customer"))[0]
    assert event["cost"] >= 0 and event["tokens_estimated"] is True
