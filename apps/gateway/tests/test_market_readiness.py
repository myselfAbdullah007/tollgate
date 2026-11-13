"""Launch-blocking regressions; all upstream work is synthetic."""

import asyncio
import base64
from datetime import UTC, datetime

import pytest
from tollgate.providers import ProviderError
from tollgate.schemas import ChatRequest

BODY = {"model": "smart", "temperature": 1, "messages": [{"role": "user", "content": "Hello"}]}


@pytest.mark.parametrize(
    "option", [{"response_format": {"type": "json_object"}}, {"max_completion_tokens": 42}, {"seed": 1}]
)
async def test_unsupported_options_fail_before_provider(client, app, auth, option):
    async def forbidden(*args):
        pytest.fail("Unsupported options must not reach a provider")

    app.state.pipeline.providers.chat = forbidden
    response = await client.post("/v1/chat/completions", headers=auth, json=dict(BODY, **option))
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == next(iter(option))


@pytest.mark.parametrize("stream", [False, True])
async def test_timeouts_preserve_unknown_cost_for_every_attempt(client, app, auth, stream):
    calls = []

    async def timeout(target, *args):
        calls.append(target)
        raise TimeoutError()

    async def stream_timeout(target, *args):
        await timeout(target)
        yield {}  # async-generator transport, never emits a client byte

    app.state.pipeline.providers.chat = timeout
    app.state.pipeline.providers.stream = stream_timeout
    response = await client.post("/v1/chat/completions", headers=auth, json=dict(BODY, stream=stream))
    assert response.status_code == 502
    event = (await app.state.repo.logs(customer="test_customer"))[0]
    assert len(calls) == 2
    assert event["cost"] > 0
    assert event["uncertain_cost"] == event["cost"]
    assert event["cost_basis"] == "conservative"
    key = "default:test_customer:" + datetime.now(UTC).strftime("%Y-%m")
    assert await app.state.fast.spend(key) == event["cost"]
    assert await app.state.fast.reserved(key) == 0


async def test_timeout_then_success_accounts_both_attempts(client, app, auth):
    original = app.state.pipeline.providers.chat
    calls = []

    async def once(target, *args):
        calls.append(target)
        if len(calls) == 1:
            raise TimeoutError()
        return await original(target, *args)

    app.state.pipeline.providers.chat = once
    response = await client.post("/v1/chat/completions", headers=auth, json=BODY)
    assert response.status_code == 200
    event = (await app.state.repo.logs(customer="test_customer"))[0]
    assert event["cost"] > event["uncertain_cost"] > 0
    assert event["tokens_estimated"] is True
    assert event["fallback_count"] == 1


async def test_cancellation_after_dispatch_preserves_reservation_cost(app):
    entered = asyncio.Event()

    async def waiting(*args):
        entered.set()
        await asyncio.Event().wait()

    app.state.pipeline.providers.chat = waiting
    task = asyncio.create_task(
        app.state.pipeline.execute(ChatRequest(**BODY).model_dump(exclude_none=True), "default", "cancelled")
    )
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    event = (await app.state.repo.logs(customer="cancelled"))[0]
    assert event["cost"] == event["uncertain_cost"] > 0
    assert not app.state.fast.inflight["default"]


async def test_confirmed_rejection_is_not_charged(client, app, auth):
    async def reject(*args):
        raise ProviderError(401)

    app.state.pipeline.providers.chat = reject
    assert (await client.post("/v1/chat/completions", headers=auth, json=BODY)).status_code == 502
    event = (await app.state.repo.logs(customer="test_customer"))[0]
    assert event["cost"] == event["uncertain_cost"] == 0


async def test_fallback_chain_is_fully_reserved_before_dispatch(client, app, auth):
    from tollgate.pricing import cost
    from tollgate.providers import token_count

    request = ChatRequest(**BODY).model_dump(exclude_none=True)
    payload = {key: value for key, value in request.items() if key not in ("user", "feature", "environment")}
    single = cost("mock/premium", token_count(payload), request["max_tokens"] * 4)
    customer = await app.state.pipeline.customer("default", "test_customer")
    await app.state.repo.put(
        "customer", customer["name"], dict(customer, budget_override=single), id=customer["id"]
    )
    plan = await app.state.repo.find("plan", customer["plan"])
    await app.state.repo.put("plan", plan["name"], dict(plan, degradation=[]), id=plan["id"])
    called = False

    async def forbidden(*args):
        nonlocal called
        called = True
        raise AssertionError("Full chain must fit before dispatch")

    app.state.pipeline.providers.chat = forbidden
    response = await client.post("/v1/chat/completions", headers=auth, json=BODY)
    assert response.status_code == 402
    assert not called


async def test_stream_cleanup_failure_still_settles_unknown_work(app):
    class BrokenStream:
        calls = 0

        async def __anext__(self):
            self.calls += 1
            if self.calls == 1:
                return {
                    "delta": {"content": "partial"},
                    "usage": {"prompt_tokens": None, "completion_tokens": -1},
                }
            raise ProviderError()

        async def aclose(self):
            raise RuntimeError("synthetic cleanup failure")

    app.state.pipeline.providers.stream = lambda *args: BrokenStream()
    response = await app.state.pipeline.execute(
        ChatRequest(**dict(BODY, stream=True)).model_dump(exclude_none=True), "default", "cleanup"
    )
    with pytest.raises(RuntimeError, match="cleanup failure"):
        async for _ in response.body_iterator:
            pass
    event = (await app.state.repo.logs(customer="cleanup"))[0]
    assert event["cost"] == event["uncertain_cost"] > 0
    assert event["input_tokens"] == event["output_tokens"] == 0
    assert not app.state.fast.inflight["default"]


async def test_cache_write_failure_does_not_discard_paid_success(client, app, auth):
    async def unavailable(*args):
        raise RuntimeError("synthetic cache outage")

    app.state.fast.cache_put = unavailable
    response = await client.post("/v1/chat/completions", headers=auth, json=dict(BODY, temperature=0))
    assert response.status_code == 200
    event = (await app.state.repo.logs(customer="test_customer"))[0]
    assert event["cost"] > 0 and event["status"] == "success"


@pytest.mark.parametrize("include_usage", [False, True])
async def test_stream_usage_option_is_honored(client, auth, include_usage):
    response = await client.post(
        "/v1/chat/completions",
        headers=auth,
        json=dict(BODY, stream=True, stream_options={"include_usage": include_usage}),
    )
    assert response.status_code == 200
    assert ('"usage":' in response.text) is include_usage


async def test_operational_metrics_include_uncertainty_without_customer_labels(client, app, auth):
    async def timeout(*args):
        raise TimeoutError()

    app.state.pipeline.providers.chat = timeout
    await client.post("/v1/chat/completions", headers=auth, json=BODY)
    metrics = (await client.get("/metrics")).text
    assert "tollgate_uncertain_requests_total 1" in metrics
    assert "tollgate_fallback_attempts_total 1" in metrics
    assert 'tollgate_request_duration_seconds_bucket{le="+Inf"} 1' in metrics
    assert "test_customer" not in metrics and "Hello" not in metrics


def test_offline_production_checks_reject_demo_and_accept_hardened_config():
    from tollgate.config import Settings
    from tollgate.preflight import production_checks

    unsafe = Settings(_env_file=None, demo=True, database_url="sqlite+aiosqlite://", redis_url="")
    assert not all(production_checks(unsafe).values())
    safe = Settings(
        _env_file=None,
        demo=False,
        enable_mock_provider=False,
        database_url="postgresql+asyncpg://fixture",
        redis_url="redis://fixture",
        cookie_secure=True,
        allowed_origin="https://console.example.com",
        admin_password="synthetic-password-123",
        master_key=base64.b64encode(b"x" * 32).decode(),
    )
    assert all(production_checks(safe).values())
    safe.master_key = "invalid-base64"
    assert not production_checks(safe)["valid_master_key"]
