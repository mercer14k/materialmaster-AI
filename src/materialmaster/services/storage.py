"""SQLAlchemy persistence; SQLite for native development, PostgreSQL for Compose."""

import os

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from materialmaster.domain.models import now


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    total: Mapped[int] = mapped_column(Integer)
    valid: Mapped[int] = mapped_column(Integer)
    invalid: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="imported")
    scan_version: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class MaterialRow(Base):
    __tablename__ = "materials"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), primary_key=True)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(60), index=True)
    material_group: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(String(500))
    raw: Mapped[dict] = mapped_column(JSON)
    data: Mapped[dict] = mapped_column(JSON)
    ingested_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    validation_status: Mapped[str] = mapped_column(String(20), default="valid")


class RejectedRow(Base):
    __tablename__ = "rejected_rows"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    raw: Mapped[dict] = mapped_column(JSON)
    errors: Mapped[list] = mapped_column(JSON)
    ingested_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class Issue(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (Index("ix_queue", "dataset_id", "status", "kind"),)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(60))
    actor: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(100), index=True)
    trace_id: Mapped[str] = mapped_column(String(80))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class Snapshot(Base):
    __tablename__ = "quality_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    metrics: Mapped[dict] = mapped_column(JSON)


class Idempotency(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)


class ModelEvent(Base):
    __tablename__ = "model_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(80))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


def database(url: str | None = None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///./materialmaster.db")
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")

    return engine, sessionmaker(engine, expire_on_commit=False)
