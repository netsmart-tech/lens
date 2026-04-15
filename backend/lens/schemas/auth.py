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
    authentik_sub: str | None = None


class TenantWithRoleResponse(BaseModel):
    """Tenant shape returned in /api/auth/me — includes the caller's role."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    color_hex: str | None = None
    logo_ref: str | None = None
    role: str  # "owner" for staff, else from lens_core.user_tenants.role


class AuthMeResponse(BaseModel):
    """Shape the frontend's auth-context expects from GET /api/auth/me."""

    user: UserResponse
    tenants: list[TenantWithRoleResponse]
