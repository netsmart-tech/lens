"""Pydantic shapes for the tenants router."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    color_hex: str | None = None
    logo_ref: str | None = None
    created_at: datetime
