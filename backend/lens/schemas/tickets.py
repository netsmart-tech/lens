"""Pydantic shapes for the tickets router."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from lens.schemas.sync import SyncBlock


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    site_id: uuid.UUID
    key: str
    summary: str
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    reporter: str | None = None
    issue_created: datetime | None = None
    issue_updated: datetime | None = None


class TicketDetailResponse(TicketResponse):
    raw: dict[str, Any] | None = None


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    sync: SyncBlock
