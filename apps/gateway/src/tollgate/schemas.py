import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .pricing import RATES as PRICES


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
    feature: str = Field(default="general", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    environment: str = Field(default="production", pattern=r"^[a-zA-Z0-9_-]{1,32}$")

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
            calls = m.get("tool_calls")
            if calls is not None and not isinstance(calls, list):
                raise ValueError("tool_calls must be an array or null")
            if calls is None:
                m.pop("tool_calls", None)
            for call in calls or []:
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
    revision: int | None = Field(default=None, ge=1)
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

    @model_validator(mode="after")
    def ordered_steps(self):
        if len(self.degradation) > 10 or any(
            current.at <= previous.at or current.tier <= previous.tier
            for previous, current in zip(self.degradation, self.degradation[1:])
        ):
            raise ValueError("At most 10 thresholds are allowed, with increasing percentages and tiers")
        return self


class Alias(BaseModel):
    revision: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    allow_degrade: bool = True
    tiers: list[list[str]] = Field(min_length=1, max_length=11)

    @model_validator(mode="after")
    def targets(self):
        if any(not tier or len(tier) > 8 or any(t not in PRICES for t in tier) for tier in self.tiers):
            raise ValueError("Each tier needs 1–8 supported, priced targets")
        return self


class Customer(BaseModel):
    revision: int | None = Field(default=None, ge=1)
    monthly_revenue: int | None = Field(default=None, ge=0, le=10**15)
    name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    plan: str = Field(min_length=1, max_length=100)
    budget_override: int | None = Field(default=None, ge=0, le=10**15)


class Tenant(BaseModel):
    revision: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    rpm: int = Field(default=1000, ge=1, le=1000000)
    default_plan: str = "Pro"


class KeyCreate(BaseModel):
    customer: str | None = Field(default=None, max_length=200)
    scope: Literal["gateway", "usage"] = "gateway"
    name: str = Field(min_length=1, max_length=100)


class Credential(BaseModel):
    provider: Literal["openai", "anthropic", "google"]
    key: str = Field(min_length=8, max_length=500)
    tenant_id: str = "default"


class Preview(BaseModel):
    tenant_id: str | None = None
    customer: str | None = None
    text: str = Field(max_length=50000)
    mode: Literal["off", "mask", "reversible", "block"] = "reversible"
    block_categories: list[str] = Field(default_factory=list)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=500)
    new_password: str = Field(min_length=12, max_length=500)


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=12, max_length=500)
    role: Literal["owner", "admin", "viewer"] = "viewer"


class WebhookConfig(BaseModel):
    url: str = Field(max_length=1000)
    enabled: bool = False

    @model_validator(mode="after")
    def public_https(self):
        import ipaddress
        from urllib.parse import urlsplit

        value = urlsplit(self.url)
        if (
            value.scheme != "https"
            or not value.hostname
            or value.username
            or value.password
            or value.fragment
        ):
            raise ValueError("A public HTTPS URL without credentials or fragments is required")
        host = value.hostname.lower()
        if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
            raise ValueError("Private webhook destinations are not allowed")
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError("Private webhook destinations are not allowed")
        except ValueError as exc:
            if "Private" in str(exc):
                raise
        return self


class UserUpdate(BaseModel):
    role: Literal["owner", "admin", "viewer"]
    disabled: bool = False
    revision: int | None = None


class Bootstrap(BaseModel):
    plans: list[Plan] = Field(default_factory=list)
    aliases: list[Alias] = Field(default_factory=list)

    @model_validator(mode="after")
    def distinct_names(self):
        for rows in (self.plans, self.aliases):
            if len({row.name for row in rows}) != len(rows):
                raise ValueError("Configuration names must be unique")
        return self
