"""lens_core.sync_state — per-(tenant, source) watermark + status."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lens.db.base import CoreBase


class SyncState(CoreBase):
    __tablename__ = "sync_state"
    __table_args__ = {"schema": "lens_core"}

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lens_core.tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="backfill")
    cursor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    backfill_complete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
