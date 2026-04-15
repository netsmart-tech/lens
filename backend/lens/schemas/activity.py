"""Pydantic shapes for the activity router."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from lens.schemas.sync import SyncBlock


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: uuid.UUID
    source: str
    actor: str
    action: str
    subject: str
    occurred_at: datetime
    metadata: dict[str, Any] | None = None


class ActivityListResponse(BaseModel):
    items: list[ActivityResponse]
    sync: SyncBlock
