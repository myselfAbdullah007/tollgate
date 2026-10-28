import asyncio
import secrets
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, BigInteger, Index, String, UniqueConstraint, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    # RFC 9562 UUIDv7, including on Python 3.12 where uuid.uuid7 is unavailable.
    value = (
        (int(time.time() * 1000) << 80)
        | (7 << 76)
        | (secrets.randbits(12) << 64)
        | (2 << 62)
        | secrets.randbits(62)
    )
    return str(uuid.UUID(int=value))


def now():
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class Record(Base):
    """Tenant-scoped configuration records; kind + tenant + name are unique."""

    __tablename__ = "records"
    __table_args__ = (UniqueConstraint("kind", "tenant_id", "name"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    name: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Log(Base):
    __tablename__ = "request_logs"
    __table_args__ = (
        Index("ix_logs_tenant_customer_time", "tenant_id", "customer_id", "created_at"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[str] = mapped_column(String(200))
    cost: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[str] = mapped_column(String(40), primary_key=True, index=True)
    data: Mapped[dict] = mapped_column(JSON)


class Daily(Base):
    __tablename__ = "usage_daily"
    __table_args__ = (UniqueConstraint("tenant_id", "customer_id", "day"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(64))
    customer_id: Mapped[str] = mapped_column(String(200))
    day: Mapped[str] = mapped_column(String(10))
    requests: Mapped[int] = mapped_column(BigInteger, default=0)
    cost: Mapped[int] = mapped_column(BigInteger, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)


class Database:
    def __init__(self, url: str):
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.partitions: set[str] = set()
        self.partition_lock = asyncio.Lock()
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def migrate(self):
        def upgrade(connection):
            cfg = Config()
            cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")

        async with self.engine.begin() as conn:
            if self.engine.dialect.name == "postgresql":
                await conn.execute(text("SELECT pg_advisory_xact_lock(741828)"))
            await conn.run_sync(upgrade)

    async def ensure_partition(self, stamp):
        if self.engine.dialect.name != "postgresql":
            return
        month = datetime.fromisoformat(stamp).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        name = "request_logs_" + month.strftime("%Y_%m")
        if name in self.partitions:
            return
        end = (
            month.replace(year=month.year + 1, month=1)
            if month.month == 12
            else month.replace(month=month.month + 1)
        )
        async with self.partition_lock:
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT pg_advisory_xact_lock(741829)"))
                # Identifiers and dates are generated from a parsed datetime, never interpolated user text.
                await conn.execute(
                    text(
                        f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF request_logs FOR VALUES FROM ('{month.isoformat()}') TO ('{end.isoformat()}')"
                    )
                )
            self.partitions.add(name)
