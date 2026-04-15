"""portal_core.activities — unified cross-source activity stream."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lens.db.base import CoreBase


class Activity(CoreBase):
    __tablename__ = "activities"
    __table_args__ = (
        # Teo: explicit dedup_key replaces composite unique (see recommendation §9)
        UniqueConstraint("tenant_id", "source", "dedup_key", name="uq_activities_dedup"),
        Index("ix_activities_tenant_occurred", "tenant_id", "occurred_at"),
        Index("ix_activities_tenant_source_occurred", "tenant_id", "source", "occurred_at"),
        {"schema": "portal_core"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_core.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(1024), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(512), nullable=False)
