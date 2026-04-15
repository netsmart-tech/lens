"""Pydantic shapes for the tickets router."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lens.schemas.sync import SyncBlock


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author: str | None = None
    body: str
    created: datetime


class TicketResponse(BaseModel):
    # The ORM columns are named `issue_created` / `issue_updated` (to avoid
    # colliding with Python/SQLAlchemy reserved names) but the frontend
    # JiraIssue contract from Zara's handoff uses shorter `created` / `updated`.
    # validation_alias maps from ORM attr name → field; default serialization
    # uses the field name so the JSON payload matches frontend expectations.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    site_id: uuid.UUID
    key: str
    summary: str
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    reporter: str | None = None
    created: datetime | None = Field(default=None, validation_alias="issue_created")
    updated: datetime | None = Field(default=None, validation_alias="issue_updated")


class TicketDetailResponse(TicketResponse):
    description: str | None = None
    comments: list[CommentResponse] = Field(default_factory=list)


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    sync: SyncBlock
