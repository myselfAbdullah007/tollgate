import asyncio
import copy
import hashlib
import json
import logging
import time
from datetime import UTC, datetime

from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from .db import now, uid
from .fastpath import BudgetExhausted
from .providers import PRICES, ProviderError, token_count
from .redaction import BlockedPII, StreamRestorer, Vault

logger = logging.getLogger("tollgate.pipeline")


class Pipeline:
    def __init__(self, repo, fast, providers):
        self.repo, self.fast, self.providers = repo, fast, providers
        self.requests = 0
        self.errors = 0

    async def customer(self, tenant, external):
        customer = await self.repo.find("customer", external, tenant)
        if not customer:
            config = await self.repo.find("tenant", tenant, "global")
            customer = await self.repo.put(
                "customer",
                external,
                {"display_name": external, "plan": config["default_plan"], "budget_override": None},
                tenant,
            )
        return customer

    async def execute(self, request, tenant, external, key_id="playground"):
        try:
            return await self._execute(request, tenant, external, key_id)
        except HTTPException as exc:
            if exc.status_code in (400, 402, 422, 429):
                event = {
                    "id": uid(),
                    "tenant_id": tenant,
                    "customer_id": external,
                    "api_key_id": key_id,
                    "alias": request["model"],
                    "tier_served": 0,
                    "provider": "none",
                    "model": "none",
                    "status": "error",
                    "http_status": exc.status_code,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "tokens_estimated": True,
                    "cost": 0,
                    "latency_ms": 0,
                    "cache_hit": False,
                    "fallback_count": 0,
                    "pii_counts": {},
                    "error_code": {
                        400: "invalid_config",
                        402: "budget_exhausted",
                        422: "pii_blocked",
                        429: "rate_limited",
                    }[exc.status_code],
                    "created_at": now(),
                }
                try:
                    if self.fast.redis:
                        await self.fast.redis.xadd("tollgate:events", {"event": json.dumps(event)})
                    else:
                        await self.repo.write_event(event)
                except Exception:
                    logger.exception("Unable to record rejection %s", event["id"])
            raise

    async def _execute(self, request, tenant, external, key_id="playground"):
        self.requests += 1
        started, request_id = time.monotonic(), uid()
        customer = await self.customer(tenant, external)
        plan = await self.repo.find("plan", customer["plan"], tenant)
        alias = await self.repo.find("alias", request["model"], tenant)
        if not plan or not alias:
            raise HTTPException(400, "Unknown plan or model alias")
        tenant_config = await self.repo.find("tenant", tenant, "global")
        if not await self.fast.rate_limit(
            [tenant + ":" + external, tenant], [plan["rpm"], tenant_config["rpm"]]
        ):
            raise HTTPException(429, "Rate limit reached", headers={"Retry-After": "60"})
        vault = Vault(plan["pii_mode"], plan.get("pii_block_categories"))
        try:
            redacted = vault.transform({k: v for k, v in request.items() if k not in ("user",)})
        except BlockedPII as exc:
            raise HTTPException(422, "Blocked sensitive category: " + str(exc)) from exc
        if vault.values and plan["pii_mode"] == "reversible":
            redacted["messages"].insert(
                0,
                {
                    "role": "system",
                    "content": "Keep all bracketed placeholders such as [EMAIL_1] exactly as written. Never invent placeholders.",
                },
            )
        period = datetime.now(UTC).strftime("%Y-%m")
        spend_key = f"{tenant}:{external}:{period}"
        await self.fast.initialize(spend_key, await self.repo.spend(tenant, external, period))
        budget = customer.get("budget_override")
        budget = plan["monthly_budget"] if budget is None else budget
        input_estimate = token_count(redacted)
        estimates = [
            max(input_estimate * PRICES[t][0] + request["max_tokens"] * 4 * PRICES[t][1] for t in tier)
            for tier in alias["tiers"]
        ]
        try:
            tier, used, estimate = await self.fast.reserve(
                spend_key,
                request_id,
                budget,
                plan["degradation"],
                estimates,
                alias["allow_degrade"],
                plan["on_exhausted"],
                plan.get("overage_cap", 0),
            )
        except BudgetExhausted as exc:
            raise HTTPException(
                402, "Customer budget exhausted. Increase the budget or change the plan."
            ) from exc
        cache_key = hashlib.sha256(
            json.dumps([tenant, alias["tiers"][tier], redacted], sort_keys=True).encode()
        ).hexdigest()
        cached = (
            await self.fast.cached(cache_key)
            if request.get("temperature") == 0 and plan["pii_mode"] != "off"
            else None
        )
        target, fallback_count, hit = alias["tiers"][tier][0], 0, cached is not None
        event = {
            "id": request_id,
            "tenant_id": tenant,
            "customer_id": external,
            "api_key_id": key_id,
            "alias": request["model"],
            "tier_served": tier,
            "pii_counts": dict(vault.counts),
            "created_at": now(),
            "input_tokens": 0,
            "output_tokens": 0,
            "tokens_estimated": True,
            "cache_hit": hit,
            "fallback_count": 0,
            "cost": 0,
            "error_code": None,
            "status": "success",
            "http_status": 200,
        }
        settled = False

        async def account(usage=None, error=False, conservative=False, estimated=False):
            nonlocal settled
            if settled:
                return
            settled = True
            usage = usage or {}
            a, b = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            actual = 0 if hit else estimate if conservative else a * PRICES[target][0] + b * PRICES[target][1]
            event.update(
                provider=target.split("/")[0],
                model=target,
                cost=actual,
                input_tokens=a,
                output_tokens=b,
                tokens_estimated=target.startswith("mock/") or not bool(usage) or estimated or conservative,
                latency_ms=round((time.monotonic() - started) * 1000),
                fallback_count=fallback_count,
                status="error" if error else "success",
                http_status=502 if error else 200,
                error_code="upstream_error" if error else None,
            )
            try:
                done = await self.fast.settle(spend_key, request_id, actual, event)
                if done and not self.fast.redis:
                    await self.repo.write_event(event)
            except Exception:
                logger.exception("Accounting failed for request %s; reservation retained", request_id)

        try:
            if cached:
                target = cached["target"]
                result = copy.deepcopy(cached["result"])
            else:
                last_error = None
                result = None
                for i, candidate in enumerate(alias["tiers"][tier]):
                    if await self.fast.breaker_open(tenant + ":" + candidate):
                        continue
                    try:
                        if request.get("stream"):
                            iterator = self.providers.stream(candidate, redacted, tenant)
                            first = await asyncio.wait_for(
                                anext(iterator), timeout=max(1, 120 - (time.monotonic() - started))
                            )
                            result = (first, iterator)
                        else:
                            result = await asyncio.wait_for(
                                self.providers.chat(candidate, redacted, tenant),
                                timeout=max(1, 120 - (time.monotonic() - started)),
                            )
                        target, fallback_count = candidate, i
                        await self.fast.success(tenant + ":" + candidate)
                        break
                    except (ProviderError, StopAsyncIteration, TimeoutError) as exc:
                        last_error = exc
                        await self.fast.failure(tenant + ":" + candidate)
                        if (
                            isinstance(exc, ProviderError)
                            and exc.status not in (429, 502, 503, 504)
                            and exc.status < 500
                        ):
                            break
                if result is None:
                    raise ProviderError() from last_error
            headers = {
                "X-Tollgate-Tier": str(tier),
                "X-Tollgate-Model-Served": target,
                "X-Tollgate-Budget-Remaining-Usd": f"{max(0, budget - used - (0 if hit else estimate)) / 1000000:.6f}",
                "X-Tollgate-Cache": "HIT" if hit else "MISS",
                "X-Request-Id": request_id,
            }
            if request.get("stream"):
                return StreamingResponse(
                    self._stream(
                        result,
                        hit,
                        target,
                        vault,
                        event,
                        account,
                        input_estimate,
                        started + 120,
                        cache_key if request.get("temperature") == 0 and plan["pii_mode"] != "off" else None,
                    ),
                    media_type="text/event-stream",
                    headers=dict(headers, **{"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}),
                )
            if request.get("temperature") == 0 and plan["pii_mode"] != "off" and not hit:
                await self.fast.cache_put(cache_key, {"target": target, "result": result})
            usage_estimated = not bool(result.get("usage"))
            usage = result.get("usage") or {
                "prompt_tokens": input_estimate,
                "completion_tokens": token_count(result["choices"]),
            }
            await account(usage, estimated=usage_estimated)
            result["usage"] = dict(
                usage,
                total_tokens=usage.get("total_tokens", usage["prompt_tokens"] + usage["completion_tokens"]),
            )
            result = copy.deepcopy(result)
            result["id"] = "chatcmpl-" + request_id
            result["model"] = target
            if hit:
                result["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            for choice in result["choices"]:
                message = choice["message"]
                if message.get("content"):
                    message["content"] = vault.restore(message["content"])
                for tool in message.get("tool_calls", []):
                    tool["function"]["arguments"] = vault.restore(tool["function"]["arguments"])
            return JSONResponse(result, headers=headers)
        except BaseException as exc:
            self.errors += 1
            await asyncio.shield(account(error=True))
            if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt)):
                raise
            raise HTTPException(502, "No healthy provider available in the selected tier") from exc

    async def _stream(self, result, hit, target, vault, event, account, input_estimate, deadline, cache_key):
        restorers = {"content": StreamRestorer(vault)}
        usage, captured, text, finished = None, [], "", False
        created = int(time.time())

        def frame(delta, reason=None, usage=None):
            return (
                "data: "
                + json.dumps(
                    {
                        "id": "chatcmpl-" + event["id"],
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": target,
                        "choices": [{"index": 0, "delta": delta, "finish_reason": reason}],
                        **({"usage": usage} if usage else {}),
                    }
                )
                + "\n\n"
            )

        async def events():
            if hit:
                for item in result:
                    yield copy.deepcopy(item)
            else:
                first, iterator = result
                yield first
                while True:
                    try:
                        yield await asyncio.wait_for(
                            anext(iterator), timeout=max(0.01, deadline - time.monotonic())
                        )
                    except StopAsyncIteration:
                        break

        try:
            yield frame({"role": "assistant"})
            finish_reason = "stop"
            async for raw in events():
                captured.append(copy.deepcopy(raw))
                delta = copy.deepcopy(raw.get("delta", {}))
                usage = raw.get("usage") or usage
                finish_reason = raw.get("finish_reason") or finish_reason
                if delta.get("content"):
                    text += delta["content"]
                    delta["content"] = restorers["content"].feed(delta["content"])
                for tool in delta.get("tool_calls", []):
                    index = tool["index"]
                    key = f"tool:{index}"
                    restorers.setdefault(key, StreamRestorer(vault))
                    fn = tool.get("function", {})
                    if "arguments" in fn:
                        text += fn["arguments"]
                        fn["arguments"] = restorers[key].feed(fn["arguments"])
                if delta:
                    yield frame(delta)
            for key, restorer in restorers.items():
                tail = restorer.flush()
                if tail:
                    yield frame(
                        {"content": tail}
                        if key == "content"
                        else {
                            "tool_calls": [{"index": int(key.split(":")[1]), "function": {"arguments": tail}}]
                        }
                    )
            usage_estimated = not bool(usage)
            if not usage:
                usage = {
                    "prompt_tokens": input_estimate,
                    "completion_tokens": token_count(text),
                    "total_tokens": input_estimate + token_count(text),
                }
            await account(usage, estimated=usage_estimated)
            if cache_key and not hit:
                await self.fast.cache_put(cache_key, {"target": target, "result": captured})
            finished = True
            yield frame({}, finish_reason)
            yield (
                "data: "
                + json.dumps(
                    {
                        "id": "chatcmpl-" + event["id"],
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": target,
                        "choices": [],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                        if hit
                        else usage,
                    }
                )
                + "\n\n"
            )
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            raise
        except Exception:
            self.errors += 1
            yield 'data: {"error":{"message":"Provider stream interrupted","type":"upstream_error"}}\n\n'
        finally:
            if not hit and isinstance(result, tuple):
                await result[1].aclose()
            if not finished:
                await asyncio.shield(account(usage, error=True, conservative=not hit))
