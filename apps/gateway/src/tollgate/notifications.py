"""Transactional, deduplicated budget alerts and opt-in signed webhook delivery."""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit

import httpx
from sqlalchemy import func, select

from .db import Log, Record, now, uid
from .security import digest


async def enqueue_alerts(session, event):
    tenant, customer_id = event["tenant_id"], event["customer_id"]

    async def config(kind, name):
        row = await session.scalar(
            select(Record).where(Record.kind == kind, Record.tenant_id == tenant, Record.name == name)
        )
        return row.data if row else None

    customer = await config("customer", customer_id)
    if not customer:
        return
    plan = await config("plan", customer["plan"])
    if not plan:
        return
    budget = customer.get("budget_override")
    budget = plan["monthly_budget"] if budget is None else budget
    period = event["created_at"][:7]
    spend = int(
        await session.scalar(
            select(func.coalesce(func.sum(Log.cost), 0)).where(
                Log.tenant_id == tenant,
                Log.customer_id == customer_id,
                Log.created_at >= period + "-01",
                Log.created_at < period + "-32",
            )
        )
        or 0
    )
    kinds = []
    for threshold in plan["degradation"]:
        if spend >= budget * threshold["at"]:
            kinds.append(("customer.budget_threshold", str(threshold["at"]), {"threshold": threshold["at"]}))
    if event.get("status") == "success" and event.get("tier_served", 0) > 0:
        kinds.append(("customer.degraded", str(event["tier_served"]), {"tier": event["tier_served"]}))
    if spend >= budget or event.get("error_code") == "budget_exhausted":
        kinds.append(("customer.budget_exhausted", "full", {}))
    webhook = await config("webhook", "budget")
    for kind, suffix, extra in kinds:
        name = digest(json.dumps([tenant, customer_id, period, kind, suffix]))
        if await session.scalar(
            select(Record.id).where(Record.kind == "alert", Record.tenant_id == tenant, Record.name == name)
        ):
            continue
        payload = {
            "id": uid(),
            "type": kind,
            "tenant_id": tenant,
            "customer_id": customer_id,
            "period": period,
            "spend": spend,
            "budget": budget,
            "created_at": now(),
            **extra,
        }
        session.add(
            Record(
                kind="alert",
                tenant_id=tenant,
                name=name,
                data={
                    "payload": payload,
                    "delivery_status": "pending" if webhook and webhook.get("enabled") else "unconfigured",
                    "attempts": 0,
                    "next_attempt": 0,
                },
            )
        )


def signature(secret: str, timestamp: str, body: bytes) -> str:
    signed = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signed}"


async def public_address(host, port):
    addresses = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    ips = [address[4][0] for address in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("Webhook DNS must resolve only to public addresses")
    return ips[0]


async def deliver(repo, crypto, tenant):
    config = await repo.find("webhook", "budget", tenant)
    if not config or not config.get("enabled"):
        return
    batch = [
        row
        for row in await repo.records("alert", tenant)
        if row["delivery_status"] in ("pending", "retry") and row["next_attempt"] <= time.time()
    ][:10]
    for item in batch:
        if item["delivery_status"] not in ("pending", "retry") or item["next_attempt"] > time.time():
            continue
        body = json.dumps(item["payload"], sort_keys=True, separators=(",", ":")).encode()
        stamp = str(int(time.time()))
        try:
            destination = httpx.URL(config["url"])
            host = urlsplit(config["url"]).hostname
            address = await public_address(host, 443)
            # Pin the validated address for this connection, while verifying the original
            # hostname through TLS SNI. No proxy, redirect, or second DNS resolution.
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
                response = await client.post(
                    destination.copy_with(host=address),
                    content=body,
                    headers={
                        "Host": host,
                        "Content-Type": "application/json",
                        "X-Tollgate-Event-Id": item["payload"]["id"],
                        "X-Tollgate-Signature": signature(
                            crypto.decrypt(config["encrypted_secret"]), stamp, body
                        ),
                    },
                    extensions={"sni_hostname": host},
                )
            if not 200 <= response.status_code < 300:
                raise ValueError("Webhook returned a non-success status")
            item.update(delivery_status="delivered", delivered_at=now(), last_error=None)
        except Exception:
            attempts = item["attempts"] + 1
            item.update(
                delivery_status="failed" if attempts >= 5 else "retry",
                next_attempt=int(time.time()) + 30 * 2**attempts,
                last_error="Delivery failed; check destination availability",
            )
        item["attempts"] += 1
        await repo.put("alert", item["name"], item, tenant, item["id"])
