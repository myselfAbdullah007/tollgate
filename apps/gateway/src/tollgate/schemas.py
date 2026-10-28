import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .providers import PRICES


class ChatRequest(BaseModel):
    model: str = Field(min_length=1, max_length=100)
    messages: list[dict] = Field(min_length=1, max_length=100)
    stream: bool = False
    temperature: float = Field(default=1, ge=0, le=2)
    max_tokens: int = Field(default=512, ge=1, le=8192)
    user: str | None = Field(default=None, max_length=200)
    tools: list[dict] | None = None
    tool_choice: str | dict | None = None
    stream_options: dict | None = None

    @model_validator(mode="after")
    def text_only(self):
        if len(json.dumps(self.model_dump()).encode()) > 262144:
            raise ValueError("Request exceeds 256 KiB")
        for m in self.messages:
            if m.get("role") not in ("system", "developer", "user", "assistant", "tool"):
                raise ValueError("Invalid message role")
            content = m.get("content")
            if content is not None and not isinstance(content, (str, list)):
                raise ValueError("Content must be text or text parts")
            if isinstance(content, list) and any(
                not isinstance(p, dict) or p.get("type") != "text" or not isinstance(p.get("text"), str)
                for p in content
            ):
                raise ValueError("Only text content is supported in v0.1")
            if m["role"] == "tool" and not isinstance(m.get("tool_call_id"), str):
                raise ValueError("Tool result requires tool_call_id")
            for call in m.get("tool_calls", []):
                try:
                    if not isinstance(call["id"], str) or not isinstance(call["function"]["name"], str):
                        raise ValueError("Invalid tool identity")
                    args = json.loads(call["function"]["arguments"])
                    if not isinstance(args, dict):
                        raise ValueError("Tool arguments must be a JSON object")
                except (KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise ValueError("Invalid tool-call arguments") from exc
        for tool in self.tools or []:
            if tool.get("type") != "function" or not isinstance(tool.get("function"), dict):
                raise ValueError("Only function tools are supported")
            function = tool["function"]
            if not isinstance(function.get("name"), str) or not isinstance(function.get("parameters"), dict):
                raise ValueError("Function tools require a name and parameter schema")
        return self


class Login(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=500)


class Step(BaseModel):
    at: float = Field(ge=0, le=1)
    tier: int = Field(ge=1, le=10)


class Plan(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    monthly_budget: int = Field(ge=0, le=10**15)
    rpm: int = Field(default=60, ge=1, le=100000)
    degradation: list[Step] = Field(default_factory=lambda: [Step(at=0.8, tier=1), Step(at=0.95, tier=2)])
    on_exhausted: Literal["block", "allow_overage"] = "block"
    overage_cap: int = Field(default=0, ge=0, le=10**15)
    pii_mode: Literal["off", "mask", "reversible", "block"] = "reversible"
    pii_block_categories: list[
        Literal["CARD", "EMAIL", "PHONE", "CNIC", "IBAN", "MYNUMBER", "IP", "SECRET"]
    ] = Field(default=["CARD"])


class Alias(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    allow_degrade: bool = True
    tiers: list[list[str]] = Field(min_length=1, max_length=11)

    @model_validator(mode="after")
    def targets(self):
        if any(not tier or len(tier) > 8 or any(t not in PRICES for t in tier) for tier in self.tiers):
            raise ValueError("Each tier needs 1–8 supported, priced targets")
        return self


class Customer(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    plan: str = Field(min_length=1, max_length=100)
    budget_override: int | None = Field(default=None, ge=0, le=10**15)


class Tenant(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    rpm: int = Field(default=1000, ge=1, le=1000000)
    default_plan: str = "Pro"


class KeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class Credential(BaseModel):
    provider: Literal["openai", "anthropic", "google"]
    key: str = Field(min_length=8, max_length=500)
    tenant_id: str = "default"


class Preview(BaseModel):
    text: str = Field(max_length=50000)
    mode: Literal["off", "mask", "reversible", "block"] = "reversible"
    block_categories: list[str] = Field(default_factory=list)
