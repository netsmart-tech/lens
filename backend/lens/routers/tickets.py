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
    mine_only: bool = True,
):
    """List Jira issues. Defaults to assignee = current user's email."""
    stmt = select(JiraIssue).order_by(JiraIssue.issue_updated.desc())
    if mine_only:
        stmt = stmt.where(JiraIssue.assignee == user.email)
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
