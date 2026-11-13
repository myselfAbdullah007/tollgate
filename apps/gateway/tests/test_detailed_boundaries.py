"""Adversarial inputs, authorization, storage failure and privacy boundaries."""

import asyncio
import json

import httpx
import pytest
import respx
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from tollgate.redaction import StreamRestorer, Vault
from tollgate.schemas import ChatRequest, WebhookConfig

BASE = {"model": "smart", "messages": [{"role": "user", "content": "Synthetic request"}]}


@pytest.mark.parametrize(
    "change",
    [
        {"messages": []},
        {"messages": [None]},
        {"messages": [{"role": "invalid"}]},
        {"messages": [{"role": "user", "content": 42}]},
        {"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": "x"}]}]},
        {"messages": [{"role": "tool", "content": "done"}]},
        {"messages": [{"role": "assistant", "tool_calls": [None]}]},
        {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [{"id": "t", "function": {"name": "f", "arguments": "[]"}}],
                }
            ]
        },
        {"max_tokens": 0},
        {"max_tokens": 8193},
        {"temperature": -1},
        {"temperature": 3},
        {"temperature": float("nan")},
        {"environment": "production/../../"},
        {"stream_options": {"include_usage": True}},
        {"stream": True, "stream_options": {"unknown": True}},
        {"tool_choice": "anything"},
        {"tool_choice": {}},
        {"tool_choice": {"type": "function", "function": {}}},
        {"tools": [{"type": "function", "function": {"name": "f", "parameters": {}, "description": 42}}]},
    ],
)
def test_invalid_chat_shapes_fail_validation(change):
    with pytest.raises(ValidationError):
        ChatRequest(**dict(BASE, **change))


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/hook",
        "https://localhost/hook",
        "https://127.0.0.1/hook",
        "https://[::1]/hook",
        "https://169.254.169.254/hook",
        "https://10.0.0.1/hook",
        "https://user:password@example.com/hook",
        "https://example.com/hook#fragment",
        "https://example.com:8443/hook",
        "https://example.com:80/hook",
    ],
)
def test_webhook_destination_contract(url):
    with pytest.raises(ValidationError):
        WebhookConfig(url=url)


@settings(max_examples=300)
@given(
    st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=150),
    st.lists(st.integers(1, 20), min_size=1, max_size=30),
)
def test_unicode_stream_roundtrip_and_injected_placeholders(prefix, sizes):
    vault = Vault()
    redacted = vault.transform(prefix + " alice@example.invalid [EMAIL_99] 📬")
    expected = vault.restore(redacted)
    restorer = StreamRestorer(vault)
    output, offset = [], 0
    for size in sizes:
        output.append(restorer.feed(redacted[offset : offset + size]))
        offset += size
    output.extend([restorer.feed(redacted[offset:]), restorer.flush()])
    assert "".join(output) == expected
    assert "[EMAIL_99]" not in expected


async def test_viewer_cannot_mutate_configuration_or_manage_users(admin, app):
    from httpx import ASGITransport, AsyncClient

    response = await admin.post(
        "/admin/v1/users",
        json={"email": "viewer@fixture.invalid", "password": "fixture-password-123", "role": "viewer"},
    )
    assert response.status_code == 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as viewer:
        assert (
            await viewer.post(
                "/admin/v1/auth/login",
                json={"email": "viewer@fixture.invalid", "password": "fixture-password-123"},
            )
        ).status_code == 200
        viewer.headers["X-Tollgate-Admin"] = "1"
        for method, path, body in [
            ("POST", "/tenants", {"name": "denied", "display_name": "Denied"}),
            ("POST", "/tenants/default/keys", {"name": "denied"}),
            ("PUT", "/providers", {"provider": "openai", "key": "synthetic-secret"}),
            ("POST", "/users", {"email": "a@b.invalid", "password": "fixture-password", "role": "owner"}),
            ("POST", "/tenants/default/playground", BASE),
        ]:
            assert (await viewer.request(method, "/admin/v1" + path, json=body)).status_code == 403
        assert (await viewer.get("/admin/v1/tenants/default/usage")).status_code == 200
        assert (await viewer.get("/admin/v1/users")).status_code == 403


async def test_disabled_user_cannot_create_new_session(admin, app):
    from httpx import ASGITransport, AsyncClient

    user = (
        await admin.post(
            "/admin/v1/users",
            json={"email": "disabled@fixture.invalid", "password": "fixture-password-123", "role": "viewer"},
        )
    ).json()
    assert (
        await admin.patch("/admin/v1/users/" + user["id"], json={"role": "viewer", "disabled": True})
    ).status_code == 200
    before = len(await app.state.repo.records("session", "global"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/v1/auth/login",
            json={"email": "disabled@fixture.invalid", "password": "fixture-password-123"},
        )
        assert response.status_code == 401
        assert "tg_session" not in response.cookies
    assert len(await app.state.repo.records("session", "global")) == before


async def test_csrf_origin_and_session_expiry(admin, app):
    for headers in [{"Origin": "https://attacker.invalid"}, {"X-Tollgate-Admin": "0"}]:
        assert (
            await admin.post("/admin/v1/tenants/default/keys", json={"name": "denied"}, headers=headers)
        ).status_code == 403
    row = (await app.state.repo.records("session", "global"))[0]
    await app.state.repo.put("session", row["name"], dict(row, expires_at=0), "global", row["id"])
    assert (await admin.get("/admin/v1/tenants")).status_code == 401


async def test_recovery_marker_is_added_even_if_event_is_already_committed(app):
    from tollgate.db import now, uid

    event = (await app.state.repo.logs())[0].copy()
    event.update(id=uid(), created_at=now(), customer_id="already-committed")
    await app.state.repo.write_event(event)
    await app.state.repo.write_event(event, recovery=True)
    assert await app.state.repo.recovery_pending("default")
    assert len(await app.state.repo.logs(customer="already-committed")) == 1


async def test_double_storage_failure_is_visible_without_logging_payload(client, app, auth, caplog):
    async def fail(*args, **kwargs):
        raise RuntimeError("synthetic storage failure")

    app.state.fast.settle = fail
    app.state.repo.write_event = fail
    response = await client.post("/v1/chat/completions", headers=auth, json=BASE)
    assert response.status_code == 200
    assert app.state.pipeline.metrics.counters["accounting_failures"] == 1
    assert "manual reconciliation required" in caplog.text
    assert "Synthetic request" not in caplog.text


@respx.mock
async def test_webhook_redirects_are_not_followed_and_retries_stop(app, monkeypatch):
    from tollgate import notifications

    async def public(*args):
        return "93.184.216.34"

    monkeypatch.setattr(notifications, "public_address", public)
    crypto = app.state.pipeline.providers.crypto
    await app.state.repo.put(
        "webhook",
        "budget",
        {
            "url": "https://example.com/hook",
            "enabled": True,
            "encrypted_secret": crypto.encrypt("synthetic-signing-secret"),
        },
    )
    await app.state.repo.put(
        "alert",
        "redirect-fixture",
        {
            "payload": {"id": "redirect-fixture"},
            "delivery_status": "pending",
            "attempts": 0,
            "next_attempt": 0,
        },
    )
    route = respx.post("https://93.184.216.34/hook").mock(
        return_value=httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})
    )
    for _ in range(5):
        row = await app.state.repo.find("alert", "redirect-fixture")
        await app.state.repo.put("alert", row["name"], dict(row, next_attempt=0), id=row["id"])
        await notifications.deliver(app.state.repo, crypto, "default")
    await notifications.deliver(app.state.repo, crypto, "default")
    row = await app.state.repo.find("alert", "redirect-fixture")
    assert row["delivery_status"] == "failed" and row["attempts"] == route.call_count == 5
    assert "synthetic-signing-secret" not in json.dumps(row)


async def test_mixed_public_private_dns_fails_closed(monkeypatch):
    from tollgate.notifications import public_address

    async def addresses(*args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", addresses)
    with pytest.raises(ValueError):
        await public_address("example.com", 443)


@pytest.mark.parametrize(
    "choice", ["none", "auto", "required", {"type": "function", "function": {"name": "lookup"}}]
)
def test_supported_tool_choices_still_validate(choice):
    request = ChatRequest(
        **dict(
            BASE,
            tool_choice=choice,
            tools=[{"type": "function", "function": {"name": "lookup", "parameters": {}, "description": ""}}],
        )
    )
    assert request.tool_choice == choice


async def test_every_administrative_route_requires_session(client, app):
    checked = 0
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/admin/") or path.endswith("/auth/login"):
            continue
        path = path.replace("{tenant_id}", "default").replace("{customer_id}", "missing")
        path = path.replace("{external_id}", "missing").replace("{id}", "missing")
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            response = await client.request(
                method, path, headers={"X-Tollgate-Admin": "1"}, **({"json": {}} if method != "GET" else {})
            )
            assert response.status_code == 401, (method, path, response.status_code)
            checked += 1
    assert checked >= 30


async def test_login_lockout_and_cookie_token_is_hashed(client, app):
    from tollgate.security import digest

    credentials = {"email": "admin@tollgate.local", "password": "tollgate-demo-2026"}
    response = await client.post("/admin/v1/auth/login", json=credentials)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    token = client.cookies["tg_session"]
    sessions = await app.state.repo.records("session", "global")
    assert token not in json.dumps(sessions) and sessions[0]["name"] == digest(token)
    for _ in range(9):
        response = await client.post("/admin/v1/auth/login", json=dict(credentials, password="incorrect"))
        assert response.status_code == 401
    limited = await client.post("/admin/v1/auth/login", json=credentials)
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"


@respx.mock
async def test_legacy_webhook_port_is_revalidated_before_network(app, monkeypatch):
    from tollgate import notifications

    async def forbidden(*args):
        pytest.fail("Invalid stored destinations must not reach DNS or HTTP")

    monkeypatch.setattr(notifications, "public_address", forbidden)
    crypto = app.state.pipeline.providers.crypto
    await app.state.repo.put(
        "webhook",
        "budget",
        {
            "url": "https://example.com:8443/hook",
            "enabled": True,
            "encrypted_secret": crypto.encrypt("fixture-secret"),
        },
    )
    await app.state.repo.put(
        "alert",
        "legacy-fixture",
        {"payload": {"id": "legacy-fixture"}, "delivery_status": "pending", "attempts": 0, "next_attempt": 0},
    )
    await notifications.deliver(app.state.repo, crypto, "default")
    assert (await app.state.repo.find("alert", "legacy-fixture"))["delivery_status"] == "retry"
