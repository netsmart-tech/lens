"""<tenant>.jira_worklogs — for time-based report templates."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lens.db.base import TenantBase


class JiraWorklog(TenantBase):
    __tablename__ = "jira_worklogs"
    __table_args__ = (
        Index("ix_jira_worklogs_issue", "site_id", "issue_key"),
        {"schema": "tenant"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    issue_key: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    author: Mapped[str | None] = mapped_column(String(320), nullable=True)
    time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    started: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
