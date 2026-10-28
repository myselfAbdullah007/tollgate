"""Reproduce review findings against an isolated temporary app and mock provider.

This records current behavior; it does not change production configuration or call
external providers. It is an audit probe, not a passing acceptance suite for fixes.
"""

import asyncio
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from tollgate.config import Settings
from tollgate.db import uid
from tollgate.main import create_app
from tollgate.providers import anthropic_payload
from tollgate.schemas import ChatRequest


async def main():
    observations = {}
    with tempfile.TemporaryDirectory(prefix="tollgate-audit-") as directory:
        app = create_app(Settings(demo=True, database_url=f"sqlite+aiosqlite:///{directory}/audit.db"))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
            ) as c:
                auth = {
                    "Authorization": "Bearer tg_live_demo_tollgate_local_only",
                    "X-Tollgate-Customer": "audit-customer",
                }
                body = {
                    "model": "smart",
                    "temperature": 0,
                    "messages": [{"role": "user", "content": "Draft a short update."}],
                }
                await c.post(
                    "/admin/v1/auth/login",
                    json={"email": "admin@tollgate.local", "password": "tollgate-demo-2026"},
                )
                c.headers["X-Tollgate-Admin"] = "1"

                malformed = dict(body, messages=[{"role": "assistant", "content": None, "tool_calls": None}])
                response = await c.post("/v1/chat/completions", headers=auth, json=malformed)
                observations["nullable_tool_calls"] = {
                    "status": response.status_code,
                    "expected": "422 validation error, never 500",
                }

                card = "4111 1111 1111 1111"
                preview = await c.post("/admin/v1/pii/preview", json={"text": card})
                actual = await c.post(
                    "/v1/chat/completions",
                    headers=auth,
                    json=dict(body, messages=[{"role": "user", "content": card}]),
                )
                observations["privacy_preview_policy"] = {
                    "preview_blocked": preview.json()["blocked"],
                    "request_status": actual.status_code,
                    "expected": "Preview uses selected customer/plan CARD block rule",
                }

                first = await c.post("/v1/chat/completions", headers=auth, json=body)
                customer = await app.state.repo.find("customer", "audit-customer")
                await app.state.repo.put(
                    "customer", customer["name"], dict(customer, budget_override=0), id=customer["id"]
                )
                repeat = await c.post("/v1/chat/completions", headers=auth, json=body)
                observations["exhausted_cache_hit"] = {
                    "first_status": first.status_code,
                    "cache_entries": len(app.state.fast.cache),
                    "repeat_status": repeat.status_code,
                    "policy": "Cache lookup follows reservation; business policy decision required",
                }

                await app.state.repo.put(
                    "customer",
                    customer["name"],
                    dict(customer, budget_override=50_000_000),
                    id=customer["id"],
                )
                key = f"default:audit-customer:{datetime.now(UTC).strftime('%Y-%m')}"
                app.state.fast.spends[key] = 48_000_000
                locked = await c.post(
                    "/v1/chat/completions", headers=auth, json=dict(body, model="clinical-summary")
                )
                stats = (await c.get("/admin/v1/tenants/default/customers")).json()
                reported = next(row for row in stats if row["name"] == "audit-customer")
                observations["reported_vs_served_tier"] = {
                    "dashboard_customer_tier": reported["tier"],
                    "actual_quality_locked_request_tier": locked.headers.get("x-tollgate-tier"),
                    "status": locked.status_code,
                }

                sample = (await app.state.repo.logs())[0].copy()
                old_id = uid()
                sample.update(
                    id=old_id,
                    customer_id="audit-old-customer",
                    created_at=(datetime.now(UTC) - timedelta(days=60)).isoformat(),
                    cost=0,
                )
                await app.state.repo.write_event(sample)
                logs = (await c.get("/admin/v1/tenants/default/logs", params={"days": 7, "q": old_id})).json()
                observations["log_date_filter"] = {
                    "requested_days": 7,
                    "old_record_days": 60,
                    "returned_total": logs["total"],
                    "expected": "The displayed date range must constrain log results",
                }

                try:
                    payload = ChatRequest(
                        model="smart",
                        messages=[
                            {"role": "system", "content": [{"type": "text", "text": "Be concise"}]},
                            {"role": "user", "content": "Hello"},
                        ],
                    )
                    anthropic_payload(payload.model_dump(exclude_none=True), "fixture-model")
                    observations["anthropic_system_parts"] = {"exception": None}
                except Exception as exc:
                    observations["anthropic_system_parts"] = {
                        "schema_accepts": True,
                        "exception": type(exc).__name__,
                        "message": str(exc),
                    }

                numeric_alias = "audit-4111111111111111"
                created = await c.post(
                    "/admin/v1/tenants/default/aliases",
                    json={"name": numeric_alias, "allow_degrade": True, "tiers": [["mock/premium"]]},
                )
                aliased = await c.post(
                    "/v1/chat/completions",
                    headers=auth,
                    json=dict(body, model=numeric_alias, messages=[{"role": "user", "content": "Hello"}]),
                )
                observations["routing_identifier_redaction"] = {
                    "alias_create_status": created.status_code,
                    "request_status": aliased.status_code,
                    "detail": aliased.json().get("detail"),
                    "expected": "PII scanning must not treat configured routing identifiers as prompt data",
                }

                unknown = await c.get("/admin/v1/tenants/not-a-workspace/plans")
                observations["unknown_workspace_collection"] = {
                    "status": unknown.status_code,
                    "body": unknown.json(),
                    "expected": "Consistent 404 for an unknown workspace",
                }
    destination = Path("docs/audits/2026-10-28/feature-probes.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(observations, indent=2) + "\n")
    print(json.dumps(observations, indent=2))


asyncio.run(main())
