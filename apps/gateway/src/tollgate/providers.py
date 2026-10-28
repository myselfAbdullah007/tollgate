"""OpenAI-shaped adapters; Gemini uses Google's official compatibility endpoint."""

import asyncio
import json
import os
import time
import uuid
from typing import Any

import httpx

BASES = {
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "anthropic": "https://api.anthropic.com/v1",
}
ENV_KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "google": "GEMINI_API_KEY"}


class ProviderError(Exception):
    def __init__(self, status=502):
        self.status = status
        super().__init__("Provider request failed")


def valid_usage(value):
    return isinstance(value, dict) and all(
        type(value.get(k)) is int and value[k] >= 0 for k in ("prompt_tokens", "completion_tokens")
    )


def token_count(value):
    # Conservative byte bound, not a model tokenizer. Explicitly flagged as estimated.
    return max(1, len(json.dumps(value, ensure_ascii=False).encode()))


def envelope(model, message, usage, finish="stop"):
    return dict(
        id="chatcmpl-" + uuid.uuid4().hex,
        object="chat.completion",
        created=int(time.time()),
        model=model,
        choices=[dict(index=0, message=message, finish_reason=finish)],
        usage=usage,
    )


def text_content(value):
    if isinstance(value, list):
        return "\n".join(p["text"] for p in value)
    return value or ""


def anthropic_payload(request, model):
    system, messages = [], []
    for m in request["messages"]:
        if m["role"] in ("system", "developer"):
            system.append(text_content(m.get("content")))
            continue
        if m["role"] == "tool":
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m["tool_call_id"],
                            "content": m.get("content", ""),
                        }
                    ],
                }
            )
            continue
        content = m.get("content") or ""
        if isinstance(content, list):
            content = [{"type": "text", "text": p["text"]} for p in content if p.get("type") == "text"]
        if m.get("tool_calls"):
            content = (
                [{"type": "text", "text": content}] if isinstance(content, str) and content else content or []
            )
            content += [
                {
                    "type": "tool_use",
                    "id": t["id"],
                    "name": t["function"]["name"],
                    "input": json.loads(t["function"]["arguments"]),
                }
                for t in m["tool_calls"]
            ]
        messages.append({"role": m["role"], "content": content})
    body = dict(
        model=model,
        messages=messages,
        max_tokens=request.get("max_tokens", 512),
        stream=request.get("stream", False),
    )
    if system:
        body["system"] = "\n".join(system)
    if "temperature" in request:
        body["temperature"] = request["temperature"]
    if request.get("tools"):
        body["tools"] = [
            dict(
                name=t["function"]["name"],
                description=t["function"].get("description", ""),
                input_schema=t["function"]["parameters"],
            )
            for t in request["tools"]
        ]
    if request.get("tool_choice"):
        choice = request["tool_choice"]
        body["tool_choice"] = (
            {"type": "tool", "name": choice["function"]["name"]}
            if isinstance(choice, dict)
            else {"type": {"required": "any"}.get(choice, choice)}
        )
    return body


class Providers:
    def __init__(self, repo, crypto, enable_mock=True):
        self.repo, self.crypto, self.enable_mock = repo, crypto, enable_mock
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10))

    async def close(self):
        await self.client.aclose()

    async def credentials(self, provider, tenant):
        row = await self.repo.find("provider", provider, tenant)
        return (
            self.crypto.decrypt(row["encrypted_key"])
            if row and row.get("encrypted_key")
            else os.getenv(ENV_KEYS[provider], "")
        )

    async def prepare(self, target, request, tenant):
        provider, model = target.split("/", 1)
        key = await self.credentials(provider, tenant)
        if not key:
            raise ProviderError(503)
        if provider == "anthropic":
            return (
                BASES[provider] + "/messages",
                {"x-api-key": key, "anthropic-version": "2023-06-01"},
                anthropic_payload(request, model),
            )
        body = {k: v for k, v in request.items() if k != "user"}
        body["model"] = model
        if body.get("stream"):
            body["stream_options"] = {"include_usage": True}
        return BASES[provider] + "/chat/completions", {"Authorization": "Bearer " + key}, body

    async def mock(self, target, request):
        if not self.enable_mock or target == "mock/outage":
            raise ProviderError(503)
        await asyncio.sleep(0.018)
        text = next((m.get("content", "") for m in reversed(request["messages"]) if m["role"] == "user"), "")
        if isinstance(text, list):
            text = " ".join(p.get("text", "") for p in text)
        answer = (
            "Here’s a draft you can use:\n\nHi there,\n\n"
            + text
            + "\n\nYour request has been received and we’re happy to help. We’ll send an update shortly.\n\nBest,\nThe team"
        )
        answer = answer[: request.get("max_tokens", 512)]
        a, b = token_count(request["messages"]), token_count(answer)
        return envelope(
            target,
            {"role": "assistant", "content": answer},
            {"prompt_tokens": a, "completion_tokens": b, "total_tokens": a + b},
        )

    async def chat(self, target, request, tenant):
        if target.startswith("mock/"):
            return await self.mock(target, request)
        url, headers, body = await self.prepare(target, dict(request, stream=False), tenant)
        try:
            response = await self.client.post(url, headers=headers, json=body)
            if response.status_code >= 400:
                raise ProviderError(response.status_code)
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError() from exc
        if target.startswith("anthropic/"):
            text = "".join(p["text"] for p in result["content"] if p["type"] == "text")
            message: dict[str, Any] = {"role": "assistant", "content": text or None}
            tools = [
                dict(
                    id=p["id"],
                    type="function",
                    function=dict(name=p["name"], arguments=json.dumps(p["input"])),
                )
                for p in result["content"]
                if p["type"] == "tool_use"
            ]
            if tools:
                message["tool_calls"] = tools
            u = result.get("usage", {})
            a, b = u.get("input_tokens", 0), u.get("output_tokens", 0)
            return envelope(
                target,
                message,
                {"prompt_tokens": a, "completion_tokens": b, "total_tokens": a + b},
                "tool_calls" if tools else "length" if result.get("stop_reason") == "max_tokens" else "stop",
            )
        return result

    async def stream(self, target, request, tenant):
        """Yield normalized {delta, usage, finish_reason} events without buffering the answer."""
        if target.startswith("mock/"):
            result = await self.mock(target, request)
            text = result["choices"][0]["message"]["content"]
            for i in range(0, len(text), 7):
                yield {"delta": {"content": text[i : i + 7]}}
                await asyncio.sleep(0.004)
            yield {"delta": {}, "usage": result["usage"], "finish_reason": "stop"}
            return
        url, headers, body = await self.prepare(target, dict(request, stream=True), tenant)
        usage: dict[str, Any] = {}
        tool_indexes: dict[int, int] = {}
        try:
            async with self.client.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code >= 400:
                    raise ProviderError(response.status_code)
                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    event = json.loads(line[6:])
                    if "error" in event:
                        raise ProviderError()
                    if not target.startswith("anthropic/"):
                        choice: dict[str, Any] = next(iter(event.get("choices") or []), {})
                        yield {
                            "delta": choice.get("delta", {}),
                            "usage": event.get("usage"),
                            "finish_reason": choice.get("finish_reason"),
                        }
                        continue
                    kind = event.get("type")
                    if kind == "message_start":
                        usage = event["message"].get("usage", {})
                    elif kind == "content_block_start" and event["content_block"]["type"] == "tool_use":
                        tool = event["content_block"]
                        index = len(tool_indexes)
                        tool_indexes[event["index"]] = index
                        yield {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": index,
                                        "id": tool["id"],
                                        "type": "function",
                                        "function": {"name": tool["name"], "arguments": ""},
                                    }
                                ]
                            }
                        }
                    elif kind == "content_block_delta":
                        delta = event["delta"]
                        if delta["type"] == "text_delta":
                            yield {"delta": {"content": delta["text"]}}
                        elif delta["type"] == "input_json_delta":
                            yield {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": tool_indexes[event["index"]],
                                            "function": {"arguments": delta["partial_json"]},
                                        }
                                    ]
                                }
                            }
                    elif kind == "message_delta":
                        usage.update(event.get("usage", {}))
                        a, b = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
                        reason = event["delta"].get("stop_reason")
                        yield {
                            "delta": {},
                            "usage": {"prompt_tokens": a, "completion_tokens": b, "total_tokens": a + b},
                            "finish_reason": "tool_calls"
                            if reason == "tool_use"
                            else "length"
                            if reason == "max_tokens"
                            else "stop",
                        }
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError() from exc
