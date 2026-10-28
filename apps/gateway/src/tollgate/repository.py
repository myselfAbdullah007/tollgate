import asyncio

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .db import Daily, Log, Record


class Repository:
    def __init__(self, db):
        self.db = db
        self.demo_write_lock = asyncio.Lock()

    async def records(self, kind, tenant="default"):
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(Record)
                    .where(Record.kind == kind, Record.tenant_id == tenant)
                    .order_by(Record.created_at)
                )
            ).all()
            return [self.public(r) for r in rows]

    @staticmethod
    def public(row):
        return dict(row.data, id=row.id, name=row.name, tenant_id=row.tenant_id, created_at=row.created_at)

    async def find(self, kind, name, tenant="default"):
        async with self.db.session() as s:
            row = await s.scalar(
                select(Record).where(Record.kind == kind, Record.name == name, Record.tenant_id == tenant)
            )
            return self.public(row) if row else None

    async def get(self, kind, id, tenant="default"):
        rows = await self.records(kind, tenant)
        return next((r for r in rows if r["id"] == id), None)

    async def put(self, kind, name, data, tenant="default", id=None):
        async with self.db.session() as s:
            row = await s.scalar(
                select(Record).where(
                    Record.kind == kind,
                    Record.tenant_id == tenant,
                    Record.id == id if id else Record.name == name,
                )
            )
            if row:
                row.name, row.data = (
                    name,
                    {k: v for k, v in data.items() if k not in ("id", "name", "tenant_id", "created_at")},
                )
            else:
                row = Record(kind=kind, name=name, tenant_id=tenant, data=data)
                s.add(row)
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                if id:
                    raise
                return await self.find(kind, name, tenant)
            return self.public(row)

    async def delete(self, kind, id, tenant="default"):
        async with self.db.session() as s:
            row = await s.scalar(
                select(Record).where(Record.kind == kind, Record.id == id, Record.tenant_id == tenant)
            )
            if not row:
                return False
            await s.delete(row)
            await s.commit()
            return True

    async def write_event(self, event):
        if self.db.engine.dialect.name == "sqlite":
            async with self.demo_write_lock:
                return await self._write_event(event)
        return await self._write_event(event)

    async def _write_event(self, event):
        await self.db.ensure_partition(event["created_at"])
        async with self.db.session() as s:
            if await s.scalar(
                select(Log.id).where(Log.id == event["id"], Log.created_at == event["created_at"])
            ):
                return
            s.add(
                Log(
                    id=event["id"],
                    tenant_id=event["tenant_id"],
                    customer_id=event["customer_id"],
                    cost=event["cost"],
                    created_at=event["created_at"],
                    data=event,
                )
            )
            day = event["created_at"][:10]
            row = await s.scalar(
                select(Daily)
                .where(
                    Daily.tenant_id == event["tenant_id"],
                    Daily.customer_id == event["customer_id"],
                    Daily.day == day,
                )
                .with_for_update()
            )
            if row is None:
                row = Daily(
                    tenant_id=event["tenant_id"],
                    customer_id=event["customer_id"],
                    day=day,
                    requests=0,
                    cost=0,
                    input_tokens=0,
                    output_tokens=0,
                )
                s.add(row)
            row.requests += 1
            row.cost += event["cost"]
            row.input_tokens += event.get("input_tokens", 0)
            row.output_tokens += event.get("output_tokens", 0)
            await s.commit()

    async def logs(self, tenant="default", customer=None, limit=200, since=None):
        async with self.db.session() as s:
            q = select(Log).where(Log.tenant_id == tenant)
            if customer:
                q = q.where(Log.customer_id == customer)
            if since:
                q = q.where(Log.created_at >= since)
            return [r.data for r in (await s.scalars(q.order_by(Log.created_at.desc()).limit(limit))).all()]

    async def spend(self, tenant, customer, period):
        async with self.db.session() as s:
            return int(
                await s.scalar(
                    select(func.coalesce(func.sum(Log.cost), 0)).where(
                        Log.tenant_id == tenant,
                        Log.customer_id == customer,
                        Log.created_at >= period + "-01",
                        Log.created_at < period + "-32",
                    )
                )
                or 0
            )

    async def daily(self, tenant):
        async with self.db.session() as s:
            rows = (await s.scalars(select(Daily).where(Daily.tenant_id == tenant))).all()
            return [
                dict(
                    day=r.day,
                    customer_id=r.customer_id,
                    requests=r.requests,
                    cost=r.cost,
                    input_tokens=r.input_tokens,
                    output_tokens=r.output_tokens,
                )
                for r in rows
            ]

    async def ledger_snapshot(self):
        """One consistent ledger snapshot for rebuilding Redis counters."""
        async with self.db.session() as session:
            if self.db.engine.dialect.name == "postgresql":
                from sqlalchemy import text

                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            rows = (await session.scalars(select(Log))).all()
            totals: dict[str, int] = {}
            ids = set()
            for row in rows:
                key = f"{row.tenant_id}:{row.customer_id}:{row.created_at[:7]}"
                totals[key] = totals.get(key, 0) + row.cost
                ids.add(row.id)
            return totals, ids
