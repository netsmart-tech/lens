"""Tickets router — Jira issues for a given tenant."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from lens.auth.deps import require_authenticated
from lens.db.tenant import TenantContext, resolve_tenant
from lens.models.core.users import User
from lens.models.tenant.jira_issues import JiraIssue
from lens.schemas.tickets import (
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
)
from lens.services.sync_envelope import with_sync_envelope

router = APIRouter(prefix="/api/{tenant}", tags=["tickets"])


@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    ctx: TenantContext = Depends(resolve_tenant),
    user: User = Depends(require_authenticated),
):
    """List Jira issues for this tenant.

    Phase 1: returns every issue in the tenant's `jira_issues` table. The sync
    worker already JQL-filters to `assignee = currentUser()` on the Atlassian
    side — where "currentUser" is the PAT owner, which may live under a
    different email domain than the Lens login user (e.g. Steve's Lens login
    is `sjensen@netsmart.tech` but his TopBuild Atlassian is
    `steven.jensen@topbuild.com`). So every row in the table already IS
    "my tickets"; app-side filtering on `user.email` would double-scope with
    the wrong identifier and return zero rows.

    When Lens grows to support multiple Netsmart staff per tenant, we'll add
    a per-user-per-tenant `atlassian_email` mapping in `lens_core` and restore
    the filter using that mapping.
    """
    stmt = select(JiraIssue).order_by(JiraIssue.issue_updated.desc())
    rows = (await ctx.session.execute(stmt)).scalars().all()

    items = [TicketResponse.model_validate(r).model_dump(mode="json") for r in rows]
    envelope = await with_sync_envelope(
        ctx.session, tenant_id=ctx.tenant.id, source="jira", items=items
    )
    return envelope


@router.get("/tickets/{site_id}/{key}", response_model=TicketDetailResponse)
async def get_ticket(
    site_id: str,
    key: str,
    ctx: TenantContext = Depends(resolve_tenant),
):
    stmt = select(JiraIssue).where(JiraIssue.site_id == site_id, JiraIssue.key == key)
    row = (await ctx.session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return row
