import json

import httpx
import pytest
import respx
from tollgate.providers import anthropic_payload


@pytest.mark.parametrize(
    "provider,url,model",
    [
        ("openai", "https://api.openai.com/v1/chat/completions", "gpt-4.1-mini"),
        (
            "google",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "gemini-2.5-flash",
        ),
    ],
)
@respx.mock
async def test_compatible_adapters(app, monkeypatch, provider, url, model):
    monkeypatch.setenv("OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY", "fake-key")
    route = respx.post(url).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "Hello [EMAIL_1]"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )
    )
    p = app.state.pipeline.providers
    response = await p.chat(
        provider + "/" + model, {"messages": [{"role": "user", "content": "Hello"}]}, "default"
    )
    assert response["usage"]["prompt_tokens"] == 10
    assert json.loads(route.calls[0].request.content)["model"] == model


@respx.mock
async def test_anthropic_tools(app, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "Using a tool"},
                    {"type": "tool_use", "id": "t1", "name": "send", "input": {"email": "[EMAIL_1]"}},
                ],
                "usage": {"input_tokens": 10, "output_tokens": 6},
                "stop_reason": "tool_use",
            },
        )
    )
    response = await app.state.pipeline.providers.chat(
        "anthropic/claude-sonnet-4-20250514",
        {"messages": [{"role": "system", "content": "Be useful"}, {"role": "user", "content": "Hello"}]},
        "default",
    )
    assert response["choices"][0]["finish_reason"] == "tool_calls"
    assert response["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "send"
    assert json.loads(route.calls[0].request.content)["system"] == "Be useful"


@pytest.mark.parametrize("provider", ["openai", "google", "anthropic"])
@respx.mock
async def test_adapter_stream(app, monkeypatch, provider):
    env = {"openai": "OPENAI_API_KEY", "google": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    monkeypatch.setenv(env[provider], "fake-key")
    if provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        events = [
            {"type": "message_start", "message": {"usage": {"input_tokens": 2}}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}},
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 1}},
        ]
    else:
        url = (
            "https://api.openai.com/v1"
            if provider == "openai"
            else "https://generativelanguage.googleapis.com/v1beta/openai"
        ) + "/chat/completions"
        events = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [], "usage": {"prompt_tokens": 2, "completion_tokens": 1}},
        ]
    respx.post(url).mock(
        return_value=httpx.Response(200, text="".join("data: " + json.dumps(e) + "\n\n" for e in events))
    )
    events = [
        e
        async for e in app.state.pipeline.providers.stream(
            provider + "/model", {"messages": [{"role": "user", "content": "Hi"}]}, "default"
        )
    ]
    assert "Hello" in str(events) and events[-1]["usage"]["completion_tokens"] == 1


def test_anthropic_input_tool_translation():
    result = anthropic_payload(
        {
            "messages": [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "t1", "function": {"name": "send", "arguments": '{"email":"[EMAIL_1]"}'}}
                    ],
                },
                {"role": "tool", "tool_call_id": "t1", "content": "sent"},
            ]
        },
        "model",
    )
    assert result["messages"][0]["content"][0]["type"] == "tool_use"
    assert result["messages"][1]["content"][0]["type"] == "tool_result"
