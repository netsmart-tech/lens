"""Pydantic shapes for the auth router."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    is_staff: bool
