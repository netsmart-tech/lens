"""Tenants router — GET /api/tenants returns tenants the user can access."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lens.auth.deps import require_authenticated
from lens.db.session import get_db
from lens.models.core.tenants import Tenant
from lens.models.core.user_tenants import UserTenant
from lens.models.core.users import User
from lens.schemas.tenants import TenantResponse

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    user: User = Depends(require_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """List tenants the current user can see.

    Staff see all (non-archived) tenants; everyone else sees only tenants they
    have a `user_tenants` row for.
    """
    if user.is_staff:
        stmt = select(Tenant).where(Tenant.archived_at.is_(None)).order_by(Tenant.slug)
    else:
        stmt = (
            select(Tenant)
            .join(UserTenant, UserTenant.tenant_id == Tenant.id)
            .where(UserTenant.user_id == user.id, Tenant.archived_at.is_(None))
            .order_by(Tenant.slug)
        )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)
