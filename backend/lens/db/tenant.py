"""Tenant resolver — turns a `/api/{tenant}/...` path param into an AsyncSession.

Per Teo recommendation §2 / DESIGN §3.4, we use `schema_translate_map` applied
at session checkout (NOT `SET search_path`, which leaks across pooled async
connections).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lens.auth.deps import require_authenticated
from lens.db.engine import get_session_factory, get_tenant_engine
from lens.db.session import get_db
from lens.models.core.tenants import Tenant
from lens.models.core.user_tenants import UserTenant
from lens.models.core.users import User


@dataclass
class TenantContext:
    """Everything a per-tenant endpoint needs: the tenant row + the AsyncSession."""

    tenant: Tenant
    session: AsyncSession


async def _load_tenant(slug: str, core_db: AsyncSession, user: User) -> Tenant:
    """Look up a tenant and verify the user has access via `user_tenants`."""
    stmt = select(Tenant).where(Tenant.slug == slug, Tenant.archived_at.is_(None))
    tenant = (await core_db.execute(stmt)).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenant '{slug}' not found")

    # Staff bypass: netsmart-staff group can see all tenants.
    if user.is_staff:
        return tenant

    access = (
        await core_db.execute(
            select(UserTenant).where(
                UserTenant.user_id == user.id, UserTenant.tenant_id == tenant.id
            )
        )
    ).scalar_one_or_none()
    if access is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this tenant")
    return tenant


async def resolve_tenant(
    tenant: str = Path(..., description="Tenant slug"),
    user: User = Depends(require_authenticated),
    core_db: AsyncSession = Depends(get_db),
) -> AsyncIterator[TenantContext]:
    """FastAPI dependency — yields a `TenantContext` with a tenant-scoped AsyncSession.

    The session's connection is configured with `schema_translate_map` so that
    every query referring to `schema="tenant"` is rewritten to the tenant's
    `lens_<slug>` schema. The map is applied at checkout and scoped to this
    session's lifecycle — no pool contamination.
    """
    row = await _load_tenant(tenant, core_db, user)

    # Pick the right engine: shared default, or a per-tenant engine for
    # physical-isolation tenants (Phase 5 escape hatch).
    engine = get_tenant_engine(row.db_url)
    factory: async_sessionmaker[AsyncSession]
    if row.db_url:
        factory = async_sessionmaker(engine, expire_on_commit=False)
    else:
        factory = get_session_factory()

    async with factory() as session:
        conn = await session.connection(
            execution_options={
                "schema_translate_map": {
                    "tenant": row.schema_name,
                    # lens_core stays as-is; it's already fully-qualified in the models.
                }
            }
        )
        # The above guarantees the connection is checked out with the map applied.
        _ = conn
        try:
            yield TenantContext(tenant=row, session=session)
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
