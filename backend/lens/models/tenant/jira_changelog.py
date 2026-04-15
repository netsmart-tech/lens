"""<tenant>.jira_changelog."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lens.db.base import TenantBase


class JiraChangelog(TenantBase):
    __tablename__ = "jira_changelog"
    __table_args__ = (
        Index("ix_jira_changelog_issue_changed", "site_id", "issue_key", "changed_at"),
        {"schema": "tenant"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    issue_key: Mapped[str] = mapped_column(String(64), nullable=False)
    author: Mapped[str | None] = mapped_column(String(320), nullable=True)
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    from_value: Mapped[str | None] = mapped_column(String, nullable=True)
    to_value: Mapped[str | None] = mapped_column(String, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
