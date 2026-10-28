import asyncio

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError

from .db import Daily, Log, Record


class RevisionConflict(Exception):
    pass


class Repository:
    def __init__(self, db):
        self.db = db
        self.demo_write_lock = asyncio.Lock()
        self.config_lock = asyncio.Lock()

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
        return dict(
            row.data,
            revision=row.data.get("revision", 1),
            id=row.id,
            name=row.name,
            tenant_id=row.tenant_id,
            created_at=row.created_at,
        )

    async def find(self, kind, name, tenant="default"):
        async with self.db.session() as s:
            row = await s.scalar(
                select(Record).where(Record.kind == kind, Record.name == name, Record.tenant_id == tenant)
            )
            return self.public(row) if row else None

    async def get(self, kind, id, tenant="default"):
        async with self.db.session() as session:
            row = await session.scalar(
                select(Record).where(Record.kind == kind, Record.id == id, Record.tenant_id == tenant)
            )
            return self.public(row) if row else None

    async def key_by_hash(self, hashed):
        async with self.db.session() as session:
            row = await session.scalar(
                select(Record).where(Record.kind == "key", Record.data["key_hash"].as_string() == hashed)
            )
            return self.public(row) if row else None

    async def put(self, kind, name, data, tenant="default", id=None):
        async with self.config_lock:
            return await self._put(kind, name, data, tenant, id)

    async def _put(self, kind, name, data, tenant, id):
        async with self.db.session() as session:
            row = await session.scalar(
                select(Record)
                .where(
                    Record.kind == kind,
                    Record.tenant_id == tenant,
                    Record.id == id if id else Record.name == name,
                )
                .with_for_update()
            )
            incoming = {
                k: v
                for k, v in data.items()
                if k not in ("id", "name", "tenant_id", "created_at", "revision")
            }
            if row:
                current = row.data.get("revision", 1)
                if data.get("revision") is not None and data["revision"] != current:
                    raise RevisionConflict("This configuration changed. Reload it before saving.")
                row.name, row.data = name, dict(row.data, **incoming, revision=current + 1)
            else:
                row = Record(kind=kind, name=name, tenant_id=tenant, data=dict(incoming, revision=1))
                session.add(row)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
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

    async def write_event(self, event, recovery=False):
        if self.db.engine.dialect.name == "sqlite":
            async with self.demo_write_lock:
                return await self._write_event(event, recovery)
        return await self._write_event(event, recovery)

    async def _write_event(self, event, recovery=False):
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
            await s.flush()
            from .notifications import enqueue_alerts

            await enqueue_alerts(s, event)
            if recovery:
                s.add(
                    Record(
                        kind="recovery",
                        tenant_id=event["tenant_id"],
                        name=event["id"],
                        data={"request_id": event["id"]},
                    )
                )
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

    @staticmethod
    def log_filters(
        tenant, customer=None, since=None, until=None, status=None, q="", feature=None, environment=None
    ):
        filters = [Log.tenant_id == tenant]
        if customer:
            filters.append(Log.customer_id == customer)
        if since:
            filters.append(Log.created_at >= since)
        if until:
            filters.append(Log.created_at < until)
        if status:
            filters.append(Log.data["status"].as_string() == status)
        if feature:
            filters.append(Log.data["feature"].as_string() == feature)
        if environment:
            filters.append(Log.data["environment"].as_string() == environment)
        if q:
            filters.append(
                or_(
                    *[
                        field.contains(q, autoescape=True)
                        for field in (
                            Log.id,
                            Log.customer_id,
                            Log.data["model"].as_string(),
                            Log.data["alias"].as_string(),
                        )
                    ]
                )
            )
        return filters

    async def log_page(self, tenant, offset=0, limit=50, **filters):
        where = self.log_filters(tenant, **filters)
        async with self.db.session() as session:
            total = await session.scalar(select(func.count()).select_from(Log).where(*where))
            rows = (
                await session.scalars(
                    select(Log)
                    .where(*where)
                    .order_by(Log.created_at.desc(), Log.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return {"items": [r.data for r in rows], "total": total}

    async def usage(self, tenant, since, until=None):
        where = self.log_filters(tenant, since=since, until=until)

        def value(key):
            return func.coalesce(Log.data[key].as_integer(), 0)

        successful = Log.data["status"].as_string() == "success"
        pii = sum(
            (
                func.coalesce(Log.data["pii_counts"][key].as_integer(), 0)
                for key in ["EMAIL", "PHONE", "CARD", "SECRET", "CNIC", "MYNUMBER", "IBAN", "IP"]
            ),
            0,
        )
        async with self.db.session() as session:
            row = (
                await session.execute(
                    select(
                        func.count(),
                        func.coalesce(func.sum(Log.cost), 0),
                        func.coalesce(func.sum(pii), 0),
                        func.coalesce(func.sum(case((Log.data["cache_hit"].as_boolean(), 1), else_=0)), 0),
                        func.coalesce(func.avg(value("latency_ms")), 0),
                        func.coalesce(func.sum(case((~successful, 1), else_=0)), 0),
                        func.count(func.distinct(case((successful, Log.customer_id), else_=None))),
                        func.coalesce(
                            func.sum(case((and_(successful, value("tier_served") > 0), 1), else_=0)), 0
                        ),
                        func.coalesce(
                            func.sum(case((Log.data["tokens_estimated"].as_boolean(), 1), else_=0)), 0
                        ),
                    ).where(*where)
                )
            ).one()
            day = func.substr(Log.created_at, 1, 10)
            daily = (
                await session.execute(
                    select(day, Log.customer_id, func.count(), func.sum(Log.cost))
                    .where(*where)
                    .group_by(day, Log.customer_id)
                    .order_by(day)
                )
            ).all()
            recent = (
                await session.scalars(select(Log).where(*where).order_by(Log.created_at.desc()).limit(6))
            ).all()
            breakdown = {}
            for label, field in [
                ("feature", func.coalesce(Log.data["feature"].as_string(), "general")),
                ("environment", func.coalesce(Log.data["environment"].as_string(), "production")),
                ("model", Log.data["model"].as_string()),
                ("customer", Log.customer_id),
            ]:
                groups = (
                    await session.execute(
                        select(field, func.count(), func.sum(Log.cost))
                        .where(*where)
                        .group_by(field)
                        .order_by(func.sum(Log.cost).desc())
                        .limit(100)
                    )
                ).all()
                breakdown[label] = [
                    {"name": name, "requests": requests, "cost": cost} for name, requests, cost in groups
                ]
            from datetime import UTC, datetime

            month_start = (
                datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
            )
            monthly = (
                await session.execute(
                    select(Log.customer_id, func.sum(Log.cost))
                    .where(Log.tenant_id == tenant, Log.created_at >= month_start)
                    .group_by(Log.customer_id)
                )
            ).all()
            latest = await session.scalar(select(func.max(Log.created_at)).where(Log.tenant_id == tenant))
        return dict(
            requests=row[0],
            cost=row[1],
            pii_protected=row[2],
            cache_hits=row[3],
            avg_latency_ms=round(row[4]),
            errors=row[5],
            active_customers=row[6],
            degraded_requests=row[7],
            estimated_requests=row[8],
            daily=[dict(day=d, customer_id=c, requests=n, cost=cost) for d, c, n, cost in daily],
            recent=[r.data for r in recent],
            breakdown=breakdown,
            monthly_customer_costs=[{"name": name, "cost": cost} for name, cost in monthly],
            sampled=False,
            last_event_at=latest,
        )

    async def recovery_pending(self, tenant):
        async with self.db.session() as session:
            return bool(
                await session.scalar(
                    select(Record.id).where(Record.kind == "recovery", Record.tenant_id == tenant).limit(1)
                )
            )

    async def recovery_records(self):
        async with self.db.session() as session:
            rows = (await session.scalars(select(Record).where(Record.kind == "recovery"))).all()
            return [self.public(row) for row in rows]
