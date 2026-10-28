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
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from . import schemas
from .config import Settings
from .db import Database, now
from .fastpath import FastPath
from .pipeline import Pipeline
from .pricing import RATES as PRICES
from .providers import ENV_KEYS, Providers
from .redaction import BlockedPII, Vault
from .repository import Repository, RevisionConflict
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
    pipeline = Pipeline(repo, fast, providers, settings.max_concurrent_requests)

    @asynccontextmanager
    async def lifespan(app):
        await db.migrate()
        await seed(repo, settings)
        yield
        await providers.close()
        if fast.redis:
            await fast.redis.aclose()
        await db.engine.dispose()

    app = FastAPI(title="Tollgate", version="0.2.0", lifespan=lifespan, docs_url=None)
    app.state.repo, app.state.fast, app.state.pipeline = repo, fast, pipeline
    from .limits import IngressLimits

    app.add_middleware(IngressLimits)
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

    from redis.exceptions import RedisError

    @app.exception_handler(RedisError)
    async def fast_path_unavailable(request, exc):
        return JSONResponse(
            {"detail": "Gateway accounting is temporarily unavailable"},
            status_code=503,
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(RevisionConflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/docs", include_in_schema=False)
    async def api_docs():
        return get_swagger_ui_html(openapi_url="openapi.json", title="Tollgate API reference")

    @app.middleware("http")
    async def guard(request, call_next):
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
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
            actor = getattr(request.state, "user", None)
            if (
                actor
                and request.method in ("POST", "PUT", "PATCH", "DELETE")
                and response.status_code < 400
                and "/auth/" not in request.url.path
            ):
                from .db import uid

                parts = request.url.path.split("/")
                tenant = parts[4] if len(parts) > 4 and parts[3] == "tenants" else "default"
                await repo.put(
                    "audit",
                    uid(),
                    {
                        "actor_id": actor["id"],
                        "method": request.method,
                        "resource": request.url.path,
                        "status": response.status_code,
                    },
                    tenant,
                )
        return response

    async def session(request: Request):
        token = request.cookies.get("tg_session", "")
        row = await repo.find("session", digest(token), "global") if token else None
        if not row or row["expires_at"] <= time.time():
            raise HTTPException(401, "Please sign in")
        current = await repo.find("user", row["email"], "global")
        if not current or current.get("disabled"):
            raise HTTPException(401, "Account unavailable")
        row["role"] = current["role"]
        request.state.user = current
        if (
            request.method != "GET"
            and row["role"] == "viewer"
            and not request.url.path.startswith("/admin/v1/auth/")
            and request.url.path != "/admin/v1/pii/preview"
        ):
            raise HTTPException(403, "Viewer accounts cannot change configuration")
        return row

    async def api_key(request: Request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Bearer API key required")
        hashed = digest(authorization[7:])
        key = await repo.key_by_hash(hashed)
        if key and not key.get("revoked_at"):
            if key.get("scope", "gateway") == "usage" and request.url.path != "/v1/usage":
                raise HTTPException(403, "This key can only read its customer's usage")
            request.state.key = key
            return key["tenant_id"], key["id"]
        raise HTTPException(401, "Invalid or revoked API key")

    async def ensure_tenant(tenant_id):
        if not await repo.find("tenant", tenant_id, "global"):
            raise HTTPException(404, "Workspace not found")

    @app.get("/healthz")
    async def health():
        return {"status": "ok", "version": "0.2.0", "demo": settings.demo}

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

    @app.get("/admin/v1/status", dependencies=[Depends(session)])
    async def system_status():
        readiness = await ready()
        worker, pending = "inline", 0
        if fast.redis:
            stamp = await fast.redis.get("tollgate:worker-heartbeat")
            worker = "running" if stamp and time.time() - float(stamp) < 60 else "unavailable"
            try:
                groups = await cast(Awaitable[list], fast.redis.xinfo_groups("tollgate:events"))
                pending = sum(
                    int(g.get("pending", 0)) + int(g.get("lag", 0) or 0)
                    for g in groups
                    if g["name"] == "ledger"
                )
            except Exception:
                worker = "starting"
        return dict(readiness, worker=worker, pending_events=pending, checked_at=now())

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
        if not await fast.rate_limit(
            ["login:" + ip, "login-account:" + digest(body.email.lower())], [60, 10]
        ):
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
        if not await fast.initialized(key):
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
            eligible_tier=tier,
            reserved=await fast.reserved(key),
            remaining=max(0, budget - spend),
            reset_at=(datetime.now(UTC).replace(day=28) + __import__("datetime").timedelta(days=4))
            .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            .isoformat(),
            pii_mode=plan["pii_mode"],
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
        await ensure_tenant(tenant_id)
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
        await ensure_tenant(tenant_id)
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
        await ensure_tenant(tenant_id)
        return [
            {k: v for k, v in row.items() if k != "key_hash"} for row in await repo.records("key", tenant_id)
        ]

    @app.post("/admin/v1/tenants/{tenant_id}/keys", dependencies=[Depends(session)])
    async def create_key(tenant_id: str, body: schemas.KeyCreate):
        await ensure_tenant(tenant_id)
        if await repo.find("key", body.name, tenant_id):
            raise HTTPException(409, "Choose a unique key name")
        if body.scope == "usage" and not body.customer:
            raise HTTPException(422, "A usage key requires a customer ID")
        raw = new_key()
        row = await repo.put(
            "key",
            body.name,
            {
                "key_hash": digest(raw),
                "prefix": raw[:16],
                "revoked_at": None,
                "last_used_at": None,
                "scope": body.scope,
                "customer": body.customer,
            },
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

    def range_start(days):
        from datetime import timedelta

        return (
            datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            - timedelta(days=max(1, min(days, 90)) - 1)
        ).isoformat()

    @app.get("/admin/v1/tenants/{tenant_id}/logs", dependencies=[Depends(session)])
    async def logs(
        tenant_id: str,
        customer: str | None = None,
        status: str | None = None,
        q: str = "",
        offset: int = 0,
        limit: int = 50,
        days: int | None = None,
        start: str | None = None,
        end: str | None = None,
        feature: str | None = None,
        environment: str | None = None,
    ):
        await ensure_tenant(tenant_id)

        def stamp(value):
            if not value:
                return None
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC).isoformat()
            except ValueError as exc:
                raise HTTPException(422, "Use an ISO date/time") from exc

        return await repo.log_page(
            tenant_id,
            offset=max(0, offset),
            limit=max(1, min(limit, 200)),
            customer=customer,
            status=status,
            q=q,
            since=stamp(start) or (range_start(days) if days else None),
            until=stamp(end),
            feature=feature,
            environment=environment,
        )

    @app.get("/admin/v1/tenants/{tenant_id}/usage", dependencies=[Depends(session)])
    async def usage(tenant_id: str, days: int = 14):
        await ensure_tenant(tenant_id)
        return await repo.usage(tenant_id, range_start(days))

    @app.get("/v1/usage")
    async def customer_usage(request: Request, identity=Depends(api_key)):
        key = request.state.key
        external = (
            key.get("customer") if key.get("scope") == "usage" else request.headers.get("x-tollgate-customer")
        )
        if not external:
            raise HTTPException(400, "Customer ID required")
        row = await repo.find("customer", external, identity[0])
        if not row:
            raise HTTPException(404, "Customer not found")
        stats = await customer_stats(row, identity[0])
        return {
            k: stats[k]
            for k in (
                "name",
                "plan",
                "spend",
                "budget",
                "reserved",
                "remaining",
                "reset_at",
                "status",
                "eligible_tier",
            )
        }

    @app.get("/admin/v1/providers", dependencies=[Depends(session)])
    async def get_providers(tenant_id: str = "default"):
        await ensure_tenant(tenant_id)
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
                    "source": "stored"
                    if row
                    else "environment"
                    if os.getenv(ENV_KEYS.get(provider, ""), "")
                    else "built-in",
                    "verified": provider == "mock" and settings.enable_mock_provider,
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

    @app.get("/admin/v1/tenants/{tenant_id}/configuration", dependencies=[Depends(session)])
    async def export_configuration(tenant_id: str):
        await ensure_tenant(tenant_id)
        result = {}
        for kind, plural in (("plan", "plans"), ("alias", "aliases")):
            result[plural] = [
                {k: v for k, v in row.items() if k not in ("id", "tenant_id", "created_at", "revision")}
                for row in await repo.records(kind, tenant_id)
            ]
        return result

    @app.post("/admin/v1/tenants/{tenant_id}/configuration/validate", dependencies=[Depends(session)])
    async def validate_configuration(tenant_id: str, body: schemas.Bootstrap):
        await ensure_tenant(tenant_id)
        return {"valid": True, "plans": len(body.plans), "aliases": len(body.aliases), "applied": False}

    @app.get("/admin/v1/tenants/{tenant_id}/alerts", dependencies=[Depends(session)])
    async def alerts_list(tenant_id: str):
        await ensure_tenant(tenant_id)
        return (await repo.records("alert", tenant_id))[-100:][::-1]

    @app.get("/admin/v1/tenants/{tenant_id}/webhook", dependencies=[Depends(session)])
    async def webhook_get(tenant_id: str):
        await ensure_tenant(tenant_id)
        row = await repo.find("webhook", "budget", tenant_id)
        return (
            {"url": row["url"], "enabled": row["enabled"], "configured": True}
            if row
            else {"url": "", "enabled": False, "configured": False}
        )

    @app.put("/admin/v1/tenants/{tenant_id}/webhook", dependencies=[Depends(session)])
    async def webhook_save(tenant_id: str, body: schemas.WebhookConfig, user=Depends(session)):
        await ensure_tenant(tenant_id)
        if user["role"] != "owner":
            raise HTTPException(403, "Owner access required to configure external delivery")
        row = await repo.find("webhook", "budget", tenant_id)
        secret = secrets.token_urlsafe(32) if not row else None
        await repo.put(
            "webhook",
            "budget",
            dict(
                body.model_dump(),
                encrypted_secret=row["encrypted_secret"] if row else crypto.encrypt(secret or ""),
            ),
            tenant_id,
        )
        return {"ok": True, **({"signing_secret": secret} if secret else {})}

    @app.put(
        "/admin/v1/tenants/{tenant_id}/customers/by-external/{external_id}", dependencies=[Depends(session)]
    )
    async def provision_customer(tenant_id: str, external_id: str, body: schemas.Customer):
        await ensure_tenant(tenant_id)
        if body.name != external_id or not await repo.find("plan", body.plan, tenant_id):
            raise HTTPException(422, "External ID must match and plan must exist")
        return await repo.put("customer", external_id, body.model_dump(exclude={"name"}), tenant_id)

    @app.post("/admin/v1/pii/preview", dependencies=[Depends(session)])
    async def preview(body: schemas.Preview):
        mode, categories = body.mode, body.block_categories
        if body.tenant_id and body.customer:
            await ensure_tenant(body.tenant_id)
            customer = await repo.find("customer", body.customer, body.tenant_id)
            tenant = await repo.find("tenant", body.tenant_id, "global")
            plan = await repo.find(
                "plan", customer["plan"] if customer else tenant["default_plan"], body.tenant_id
            )
            mode, categories = plan["pii_mode"], plan.get("pii_block_categories", [])
        vault = Vault(mode, categories)
        try:
            redacted = vault.transform(body.text)
        except BlockedPII as exc:
            return {
                "blocked": True,
                "category": str(exc),
                "redacted": None,
                "counts": dict(vault.counts),
                "effective_mode": mode,
            }
        return {"redacted": redacted, "counts": dict(vault.counts), "blocked": False, "effective_mode": mode}

    @app.post("/admin/v1/tenants/{tenant_id}/playground", dependencies=[Depends(session)])
    async def playground(tenant_id: str, body: schemas.ChatRequest):
        await ensure_tenant(tenant_id)
        return await pipeline.execute(
            body.model_dump(exclude_none=True), tenant_id, body.user or "playground"
        )

    from .admin_security import routes as security_routes

    app.include_router(security_routes(repo, session))
    return app
