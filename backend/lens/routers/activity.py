"""Activity router — recent activity rows for a tenant."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from lens.db.tenant import TenantContext, resolve_tenant
from lens.models.core.activities import Activity
from lens.schemas.activity import ActivityListResponse, ActivityResponse
from lens.services.sync_envelope import with_sync_envelope

router = APIRouter(prefix="/api/{tenant}", tags=["activity"])


@router.get("/activity", response_model=ActivityListResponse)
async def list_activity(
    ctx: TenantContext = Depends(resolve_tenant),
    source: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    stmt = (
        select(Activity)
        .where(Activity.tenant_id == ctx.tenant.id)
        .order_by(Activity.occurred_at.desc())
        .limit(limit)
    )
    if source:
        stmt = stmt.where(Activity.source == source)
    rows = (await ctx.session.execute(stmt)).scalars().all()
    items = []
    for r in rows:
        # Rename metadata_ -> metadata for the response
        items.append(
            ActivityResponse(
                id=r.id,
                tenant_id=r.tenant_id,
                source=r.source,
                actor=r.actor,
                action=r.action,
                subject=r.subject,
                occurred_at=r.occurred_at,
                metadata=r.metadata_,
            ).model_dump(mode="json")
        )

    effective_source = source or "jira"
    return await with_sync_envelope(
        ctx.session, tenant_id=ctx.tenant.id, source=effective_source, items=items
    )
