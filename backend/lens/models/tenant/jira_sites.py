"""<tenant>.jira_sites — supports >1 Jira per tenant (Teo revision)."""

from __future__ import annotations

import uuid

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lens.db.base import TenantBase


class JiraSite(TenantBase):
    __tablename__ = "jira_sites"
    __table_args__ = {"schema": "tenant"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    base_url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
