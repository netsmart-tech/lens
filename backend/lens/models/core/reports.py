"""portal_core.reports — generated client reports (Phase 3 populates)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lens.db.base import CoreBase


class Report(CoreBase):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_tenant_period", "tenant_id", "period_end"),
        {"schema": "portal_core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_core.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    template: Mapped[str] = mapped_column(String(128), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    author: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portal_core.users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    markdown_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pdf_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    share_slug: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
