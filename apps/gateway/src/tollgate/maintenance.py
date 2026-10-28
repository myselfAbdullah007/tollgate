"""Explicit maintenance operations. Secrets are read in memory and never printed."""

import getpass
import os

from sqlalchemy import select

from .db import Record
from .security import Crypto, passwords


async def reset_password(repo, email):
    value = getpass.getpass("New owner password (12+ characters): ")
    repeated = getpass.getpass("Repeat password: ")
    if len(value) < 12 or value != repeated:
        raise ValueError("Passwords must match and contain at least 12 characters")
    user = await repo.find("user", email, "global")
    if not user:
        raise ValueError("Owner account not found")
    await repo.put("user", email, dict(user, password_hash=passwords.hash(value)), "global", user["id"])
    for row in await repo.records("session", "global"):
        if row["email"] == email:
            await repo.delete("session", row["id"], "global")
    print("Password reset and all sessions revoked.")


async def rotate_master_key(db, settings):
    old = Crypto(settings.master_key)
    new = Crypto(os.environ["TOLLGATE_NEW_MASTER_KEY"])
    count = 0
    async with db.session() as session:
        rows = (
            await session.scalars(
                select(Record).where(Record.kind.in_(["provider", "webhook"])).with_for_update()
            )
        ).all()
        for row in rows:
            data = dict(row.data)
            for field in ["encrypted_key", "encrypted_secret"]:
                if data.get(field):
                    data[field] = new.encrypt(old.decrypt(data[field]))
                    count += 1
            data["key_version"] = data.get("key_version", 1) + 1
            data["revision"] = data.get("revision", 1) + 1
            row.data = data
        await session.commit()
    print(
        f"Re-encrypted {count} secrets in one transaction. Set TOLLGATE_MASTER_KEY to the new key before restarting gateway and worker."
    )
