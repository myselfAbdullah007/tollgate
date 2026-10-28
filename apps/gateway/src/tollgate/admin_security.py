"""Deployment administration: live roles, password changes, session revocation."""

import time

from fastapi import APIRouter, Depends, HTTPException, Response

from . import schemas
from .security import passwords, verify_password


def routes(repo, session):
    router = APIRouter(prefix="/admin/v1", dependencies=[Depends(session)])

    async def owner(user=Depends(session)):
        if user["role"] != "owner":
            raise HTTPException(403, "Owner access required")
        return user

    @router.get("/auth/sessions")
    async def sessions(user=Depends(session)):
        rows = await repo.records("session", "global")
        return [
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "expires_at": r["expires_at"],
                "current": r["id"] == user["id"],
            }
            for r in rows
            if r["email"] == user["email"] and r["expires_at"] > time.time()
        ]

    @router.delete("/auth/sessions/{id}")
    async def revoke(id: str, response: Response, user=Depends(session)):
        row = await repo.get("session", id, "global")
        if not row or row["email"] != user["email"]:
            raise HTTPException(404, "Session not found")
        await repo.delete("session", id, "global")
        if id == user["id"]:
            response.delete_cookie("tg_session", path="/")
        return {"ok": True}

    @router.post("/auth/password")
    async def change_password(body: schemas.PasswordChange, response: Response, user=Depends(session)):
        row = await repo.find("user", user["email"], "global")
        if not verify_password(row["password_hash"], body.current_password):
            raise HTTPException(400, "Current password is incorrect")
        await repo.put(
            "user",
            row["name"],
            dict(row, password_hash=passwords.hash(body.new_password)),
            "global",
            row["id"],
        )
        for item in await repo.records("session", "global"):
            if item["email"] == user["email"]:
                await repo.delete("session", item["id"], "global")
        response.delete_cookie("tg_session", path="/")
        return {"ok": True, "message": "Password changed. Sign in again; all previous sessions were revoked."}

    @router.get("/users", dependencies=[Depends(owner)])
    async def users():
        return [
            {k: v for k, v in row.items() if k != "password_hash"}
            for row in await repo.records("user", "global")
        ]

    @router.post("/users", dependencies=[Depends(owner)])
    async def add_user(body: schemas.UserCreate):
        if await repo.find("user", body.email, "global"):
            raise HTTPException(409, "Account already exists")
        row = await repo.put(
            "user", body.email, {"password_hash": passwords.hash(body.password), "role": body.role}, "global"
        )
        return {k: v for k, v in row.items() if k != "password_hash"}

    @router.patch("/users/{id}", dependencies=[Depends(owner)])
    async def edit_user(id: str, body: schemas.UserUpdate, user=Depends(owner)):
        row = await repo.get("user", id, "global")
        if not row:
            raise HTTPException(404, "Account not found")
        if row["name"] == user["email"] and (body.disabled or body.role != "owner"):
            raise HTTPException(409, "You cannot disable or demote your own owner account")
        saved = await repo.put("user", row["name"], dict(row, **body.model_dump()), "global", id)
        if body.disabled:
            for session_row in await repo.records("session", "global"):
                if session_row["email"] == row["name"]:
                    await repo.delete("session", session_row["id"], "global")
        return {k: v for k, v in saved.items() if k != "password_hash"}

    @router.get("/tenants/{tenant_id}/audit")
    async def audit(tenant_id: str):
        if not await repo.find("tenant", tenant_id, "global"):
            raise HTTPException(404, "Workspace not found")
        return (await repo.records("audit", tenant_id))[-100:][::-1]

    return router
