"""<tenant>.jira_issue_links — blocks / clones / relates-to."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lens.db.base import TenantBase


class JiraIssueLink(TenantBase):
    __tablename__ = "jira_issue_links"
    __table_args__ = (
        Index("ix_jira_issue_links_from", "site_id", "from_key"),
        {"schema": "tenant"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_key: Mapped[str] = mapped_column(String(64), nullable=False)
    to_key: Mapped[str] = mapped_column(String(64), nullable=False)
    link_type: Mapped[str] = mapped_column(String(64), nullable=False)
