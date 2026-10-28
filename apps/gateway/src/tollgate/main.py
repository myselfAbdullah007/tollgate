import base64
import os
import secrets
import time
from collections.abc import Awaitable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from . import schemas
from .config import Settings
from .db import Database, now
from .fastpath import FastPath
from .pipeline import Pipeline
from .providers import ENV_KEYS, PRICES, Providers
from .redaction import BlockedPII, Vault
from .repository import Repository
from .security import Crypto, digest, new_key, verify_password
from .seed import seed


def create_app(settings=None):
    settings = settings or Settings()
    settings.validate_secrets()
    db = Database(settings.database_url)
    repo, fast = Repository(db), FastPath(settings.redis_url)
    crypto = Crypto(
        settings.master_key or base64.b64encode(bytes.fromhex(digest("tollgate-local-demo-only"))).decode()
    )
    providers = Providers(repo, crypto, settings.enable_mock_provider)
    pipeline = Pipeline(repo, fast, providers)

    @asynccontextmanager
    async def lifespan(app):
        await db.migrate()
        await seed(repo, settings)
        yield
        await providers.close()
        if fast.redis:
            await fast.redis.aclose()
        await db.engine.dispose()

    app = FastAPI(title="Tollgate", version="0.1.0", lifespan=lifespan)
    app.state.repo, app.state.fast, app.state.pipeline = repo, fast, pipeline
    origins = [v.strip() for v in settings.allowed_origin.split(",")]
    if settings.demo:
        origins += ["http://localhost:3187", "http://127.0.0.1:3187"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Tollgate-Customer", "X-Tollgate-Admin"],
        expose_headers=[
            "X-Tollgate-Tier",
            "X-Tollgate-Model-Served",
            "X-Tollgate-Budget-Remaining-Usd",
            "X-Tollgate-Cache",
            "X-Request-Id",
        ],
    )

    @app.middleware("http")
    async def guard(request, call_next):
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            if int(request.headers.get("content-length", "0")) > 300000:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
            if request.url.path.startswith("/admin/"):
                origin = request.headers.get("origin")
                if origin and origin not in (*origins, str(request.base_url).rstrip("/")):
                    return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
                if (
                    request.url.path != "/admin/v1/auth/login"
                    and request.headers.get("x-tollgate-admin") != "1"
                ):
                    return JSONResponse({"detail": "Admin request header required"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/admin/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    async def session(request: Request):
        token = request.cookies.get("tg_session", "")
        row = await repo.find("session", digest(token), "global") if token else None
        if not row or row["expires_at"] <= time.time():
            raise HTTPException(401, "Please sign in")
        if request.method != "GET" and row["role"] == "viewer":
            raise HTTPException(403, "Viewer accounts cannot change configuration")
        return row

    async def api_key(request: Request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Bearer API key required")
        hashed = digest(authorization[7:])
        # Read the authoritative store so revocation takes effect immediately.
        tenants = await repo.records("tenant", "global")
        for tenant in tenants:
            for key in await repo.records("key", tenant["name"]):
                if secrets.compare_digest(key["key_hash"], hashed) and not key.get("revoked_at"):
                    return tenant["name"], key["id"]
        raise HTTPException(401, "Invalid or revoked API key")

    async def ensure_tenant(tenant_id):
        if not await repo.find("tenant", tenant_id, "global"):
            raise HTTPException(404, "Workspace not found")

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "version": "0.1.0", "demo": settings.demo}

    @app.get("/readyz")
    async def ready():
        try:
            async with db.session() as s:
                await s.execute(text("SELECT 1"))
            if fast.redis:
                await cast(Awaitable[bool], fast.redis.ping())
            return {
                "status": "ready",
                "storage": "postgres" if "postgres" in settings.database_url else "sqlite",
                "fast_path": "redis" if fast.redis else "memory",
            }
        except Exception as exc:
            raise HTTPException(503, "Storage unavailable") from exc

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics():
        return (
            "# TYPE tollgate_requests_total counter\ntollgate_requests_total "
            + str(pipeline.requests)
            + "\n# TYPE tollgate_errors_total counter\ntollgate_errors_total "
            + str(pipeline.errors)
            + "\n"
        )

    @app.post("/v1/chat/completions")
    async def chat(body: schemas.ChatRequest, request: Request, identity=Depends(api_key)):
        tenant, key_id = identity
        external = request.headers.get("x-tollgate-customer") or body.user
        if not external or len(external) > 200:
            raise HTTPException(400, "Provide X-Tollgate-Customer or user (1–200 characters)")
        return await pipeline.execute(body.model_dump(exclude_none=True), tenant, external, key_id)

    @app.get("/v1/models")
    async def models(identity=Depends(api_key)):
        return {
            "object": "list",
            "data": [
                dict(id=a["name"], object="model", owned_by="tollgate")
                for a in await repo.records("alias", identity[0])
            ],
        }

    @app.post("/admin/v1/auth/login")
    async def login(body: schemas.Login, request: Request, response: Response):
        ip = request.client.host if request.client else "unknown"
        if not await fast.rate_limit(["login:" + ip], [10]):
            raise HTTPException(429, "Too many login attempts", headers={"Retry-After": "60"})
        user = await repo.find("user", body.email, "global")
        if not user or not verify_password(user["password_hash"], body.password):
            raise HTTPException(401, "Email or password is incorrect")
        token = secrets.token_urlsafe(32)
        await repo.put(
            "session",
            digest(token),
            {"email": body.email, "role": user["role"], "expires_at": time.time() + 43200},
            "global",
        )
        response.set_cookie(
            "tg_session",
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=43200,
            path="/",
        )
        return {"email": body.email, "role": user["role"]}

    @app.get("/admin/v1/auth/me")
    async def me(user=Depends(session)):
        return {"email": user["email"], "role": user["role"], "demo": settings.demo}

    @app.post("/admin/v1/auth/logout")
    async def logout(response: Response, user=Depends(session)):
        await repo.delete("session", user["id"], "global")
        response.delete_cookie("tg_session", path="/")
        return {"ok": True}

    @app.get("/admin/v1/tenants", dependencies=[Depends(session)])
    async def tenants():
        return await repo.records("tenant", "global")

    @app.post("/admin/v1/tenants", dependencies=[Depends(session)])
    async def create_tenant(body: schemas.Tenant):
        if await repo.find("tenant", body.name, "global"):
            raise HTTPException(409, "Workspace slug already exists")
        if not await repo.find("plan", body.default_plan, "default"):
            raise HTTPException(422, "Choose an existing template plan for new workspaces")
        result = await repo.put("tenant", body.name, body.model_dump(exclude={"name"}), "global")
        for kind in ("plan", "alias"):
            for row in await repo.records(kind, "default"):
                await repo.put(
                    kind,
                    row["name"],
                    {k: v for k, v in row.items() if k not in ("id", "name", "tenant_id", "created_at")},
                    body.name,
                )
        return result

    @app.patch("/admin/v1/tenants/{tenant_id}", dependencies=[Depends(session)])
    async def edit_tenant(tenant_id: str, body: schemas.Tenant):
        await ensure_tenant(tenant_id)
        if body.name != tenant_id:
            raise HTTPException(422, "Workspace slugs are immutable")
        if not await repo.find("plan", body.default_plan, tenant_id):
            raise HTTPException(422, "Default plan does not exist in this workspace")
        return await repo.put("tenant", tenant_id, body.model_dump(exclude={"name"}), "global")

    async def customer_stats(row, tenant):
        plan = await repo.find("plan", row["plan"], tenant)
        period = datetime.now(UTC).strftime("%Y-%m")
        key = f"{tenant}:{row['name']}:{period}"
        await fast.initialize(key, await repo.spend(tenant, row["name"], period))
        spend = await fast.spend(key)
        budget = (
            row.get("budget_override") if row.get("budget_override") is not None else plan["monthly_budget"]
        )
        ratio = spend / budget if budget else 1
        tier = max([0] + [s["tier"] for s in plan["degradation"] if ratio >= s["at"]])
        return dict(
            row,
            spend=spend,
            budget=budget,
            ratio=ratio,
            tier=tier,
            status="exhausted" if spend >= budget else "degraded" if tier else "healthy",
        )

    @app.get("/admin/v1/tenants/{tenant_id}/customers", dependencies=[Depends(session)])
    async def customers(tenant_id: str):
        await ensure_tenant(tenant_id)
        return [await customer_stats(row, tenant_id) for row in await repo.records("customer", tenant_id)]

    @app.get("/admin/v1/tenants/{tenant_id}/customers/{customer_id}", dependencies=[Depends(session)])
    async def customer_detail(tenant_id: str, customer_id: str):
        row = await repo.get("customer", customer_id, tenant_id)
        if not row:
            raise HTTPException(404, "Customer not found")
        return dict(await customer_stats(row, tenant_id), logs=await repo.logs(tenant_id, row["name"]))

    @app.post("/admin/v1/tenants/{tenant_id}/customers", dependencies=[Depends(session)])
    async def create_customer(tenant_id: str, body: schemas.Customer):
        await ensure_tenant(tenant_id)
        if not await repo.find("plan", body.plan, tenant_id):
            raise HTTPException(422, "Unknown plan")
        if await repo.find("customer", body.name, tenant_id):
            raise HTTPException(409, "Customer ID already exists")
        return await repo.put("customer", body.name, body.model_dump(exclude={"name"}), tenant_id)

    @app.patch("/admin/v1/tenants/{tenant_id}/customers/{id}", dependencies=[Depends(session)])
    async def edit_customer(tenant_id: str, id: str, body: schemas.Customer):
        row = await repo.get("customer", id, tenant_id)
        if not row:
            raise HTTPException(404, "Customer not found")
        if body.name != row["name"]:
            raise HTTPException(422, "Customer external IDs are immutable")
        if not await repo.find("plan", body.plan, tenant_id):
            raise HTTPException(422, "Unknown plan")
        return await repo.put("customer", body.name, body.model_dump(exclude={"name"}), tenant_id, id)

    @app.get("/admin/v1/tenants/{tenant_id}/plans", dependencies=[Depends(session)])
    async def plans(tenant_id: str):
        return await repo.records("plan", tenant_id)

    @app.post("/admin/v1/tenants/{tenant_id}/plans", dependencies=[Depends(session)])
    async def create_plan(tenant_id: str, body: schemas.Plan):
        await ensure_tenant(tenant_id)
        if await repo.find("plan", body.name, tenant_id):
            raise HTTPException(409, "Plan name already exists")
        return await repo.put("plan", body.name, body.model_dump(exclude={"name"}), tenant_id)

    @app.patch("/admin/v1/tenants/{tenant_id}/plans/{id}", dependencies=[Depends(session)])
    async def edit_plan(tenant_id: str, id: str, body: schemas.Plan):
        row = await repo.get("plan", id, tenant_id)
        if not row:
            raise HTTPException(404, "Plan not found")
        if body.name != row["name"]:
            raise HTTPException(422, "Plan names are immutable")
        return await repo.put("plan", body.name, body.model_dump(exclude={"name"}), tenant_id, id)

    @app.delete("/admin/v1/tenants/{tenant_id}/plans/{id}", dependencies=[Depends(session)])
    async def delete_plan(tenant_id: str, id: str):
        row = await repo.get("plan", id, tenant_id)
        if not row:
            raise HTTPException(404, "Plan not found")
        tenant = await repo.find("tenant", tenant_id, "global")
        if row["name"] == tenant["default_plan"] or any(
            c["plan"] == row["name"] for c in await repo.records("customer", tenant_id)
        ):
            raise HTTPException(409, "Move customers and change the default before deleting this plan")
        await repo.delete("plan", id, tenant_id)
        return {"ok": True}

    @app.get("/admin/v1/tenants/{tenant_id}/aliases", dependencies=[Depends(session)])
    async def aliases(tenant_id: str):
        return await repo.records("alias", tenant_id)

    @app.post("/admin/v1/tenants/{tenant_id}/aliases", dependencies=[Depends(session)])
    async def create_alias(tenant_id: str, body: schemas.Alias):
        await ensure_tenant(tenant_id)
        if await repo.find("alias", body.name, tenant_id):
            raise HTTPException(409, "Alias already exists")
        return await repo.put("alias", body.name, body.model_dump(exclude={"name"}), tenant_id)

    @app.patch("/admin/v1/tenants/{tenant_id}/aliases/{id}", dependencies=[Depends(session)])
    async def edit_alias(tenant_id: str, id: str, body: schemas.Alias):
        row = await repo.get("alias", id, tenant_id)
        if not row:
            raise HTTPException(404, "Alias not found")
        if body.name != row["name"]:
            raise HTTPException(422, "Alias names are immutable")
        return await repo.put("alias", body.name, body.model_dump(exclude={"name"}), tenant_id, id)

    @app.delete("/admin/v1/tenants/{tenant_id}/aliases/{id}", dependencies=[Depends(session)])
    async def delete_alias(tenant_id: str, id: str):
        if not await repo.delete("alias", id, tenant_id):
            raise HTTPException(404, "Alias not found")
        return {"ok": True}

    @app.get("/admin/v1/tenants/{tenant_id}/keys", dependencies=[Depends(session)])
    async def keys(tenant_id: str):
        return [
            {k: v for k, v in row.items() if k != "key_hash"} for row in await repo.records("key", tenant_id)
        ]

    @app.post("/admin/v1/tenants/{tenant_id}/keys", dependencies=[Depends(session)])
    async def create_key(tenant_id: str, body: schemas.KeyCreate):
        await ensure_tenant(tenant_id)
        if await repo.find("key", body.name, tenant_id):
            raise HTTPException(409, "Choose a unique key name")
        raw = new_key()
        row = await repo.put(
            "key",
            body.name,
            {"key_hash": digest(raw), "prefix": raw[:16], "revoked_at": None, "last_used_at": None},
            tenant_id,
        )
        return dict({k: v for k, v in row.items() if k != "key_hash"}, key=raw)

    @app.delete("/admin/v1/tenants/{tenant_id}/keys/{id}", dependencies=[Depends(session)])
    async def revoke_key(tenant_id: str, id: str):
        row = await repo.get("key", id, tenant_id)
        if not row:
            raise HTTPException(404, "Key not found")
        row["revoked_at"] = now()
        await repo.put("key", row["name"], row, tenant_id, id)
        return {"ok": True}

    @app.get("/admin/v1/tenants/{tenant_id}/logs", dependencies=[Depends(session)])
    async def logs(
        tenant_id: str,
        customer: str | None = None,
        status: str | None = None,
        q: str = "",
        offset: int = 0,
        limit: int = 50,
    ):
        rows = await repo.logs(tenant_id, customer, limit=10000)
        rows = [
            r
            for r in rows
            if (not status or r["status"] == status)
            and (not q or q.lower() in str([r["id"], r["customer_id"], r["model"], r["alias"]]).lower())
        ]
        return {"items": rows[max(0, offset) : max(0, offset) + max(1, min(limit, 200))], "total": len(rows)}

    @app.get("/admin/v1/tenants/{tenant_id}/usage", dependencies=[Depends(session)])
    async def usage(tenant_id: str, days: int = 14):
        from datetime import timedelta

        days = max(1, min(days, 90))
        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        rows = await repo.logs(tenant_id, limit=10000, since=since)
        daily = await repo.daily(tenant_id)
        selected = [d for d in daily if d["day"] >= since[:10]]
        return {
            "requests": sum(d["requests"] for d in selected),
            "cost": sum(d["cost"] for d in selected),
            "pii_protected": sum(sum(r.get("pii_counts", {}).values()) for r in rows),
            "cache_hits": sum(r.get("cache_hit", False) for r in rows),
            "avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / max(1, len(rows))),
            "errors": sum(r["status"] == "error" for r in rows),
            "daily": selected,
            "recent": rows[:6],
            "sampled": len(rows) == 10000,
        }

    @app.get("/admin/v1/providers", dependencies=[Depends(session)])
    async def get_providers(tenant_id: str = "default"):
        results = []
        for provider in ["openai", "anthropic", "google", "mock"]:
            row = await repo.find("provider", provider, tenant_id)
            configured = (
                provider == "mock"
                and settings.enable_mock_provider
                or bool(row and row.get("encrypted_key"))
                or bool(os.getenv(ENV_KEYS.get(provider, ""), ""))
            )
            results.append(
                {
                    "name": provider,
                    "configured": configured,
                    "source": "environment"
                    if os.getenv(ENV_KEYS.get(provider, ""), "")
                    else "stored"
                    if row
                    else "built-in",
                    "models": [t for t in PRICES if t.startswith(provider + "/")],
                }
            )
        return results

    @app.put("/admin/v1/providers", dependencies=[Depends(session)])
    async def save_provider(body: schemas.Credential):
        await ensure_tenant(body.tenant_id)
        await repo.put(
            "provider",
            body.provider,
            {"encrypted_key": crypto.encrypt(body.key), "key_version": 1},
            body.tenant_id,
        )
        return {"ok": True}

    @app.post("/admin/v1/pii/preview", dependencies=[Depends(session)])
    async def preview(body: schemas.Preview):
        vault = Vault(body.mode, body.block_categories)
        try:
            redacted = vault.transform(body.text)
        except BlockedPII as exc:
            return {"blocked": True, "category": str(exc), "redacted": None, "counts": dict(vault.counts)}
        return {"redacted": redacted, "counts": dict(vault.counts), "blocked": False}

    @app.post("/admin/v1/tenants/{tenant_id}/playground", dependencies=[Depends(session)])
    async def playground(tenant_id: str, body: schemas.ChatRequest):
        await ensure_tenant(tenant_id)
        return await pipeline.execute(
            body.model_dump(exclude_none=True), tenant_id, body.user or "playground"
        )

    return app
