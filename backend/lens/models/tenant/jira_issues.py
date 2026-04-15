"""<tenant>.jira_issues — PK (site_id, key) supports multiple Jira sites per tenant."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lens.db.base import TenantBase


class JiraIssue(TenantBase):
    __tablename__ = "jira_issues"
    __table_args__ = (
        Index("ix_jira_issues_assignee_status", "assignee", "status"),
        Index("ix_jira_issues_updated", "issue_updated"),
        {"schema": "tenant"},
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.jira_sites.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reporter: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Jira-native timestamps (see Teo §7 — separate from row lifecycle)
    issue_created: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issue_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Row-lifecycle timestamps
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
