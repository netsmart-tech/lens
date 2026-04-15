"""Tickets router — Jira issues for a given tenant."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from lens.auth.deps import require_authenticated
from lens.db.tenant import TenantContext, resolve_tenant
from lens.models.core.users import User
from lens.models.tenant.jira_comments import JiraComment
from lens.models.tenant.jira_issues import JiraIssue
from lens.schemas.tickets import (
    CommentResponse,
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
)
from lens.services.sync_envelope import with_sync_envelope

router = APIRouter(prefix="/api/{tenant}", tags=["tickets"])


def _adf_to_text(node: Any) -> str:
    """Flatten an Atlassian Document Format node to plain text.

    Jira Cloud stores ticket descriptions + comments as ADF JSON trees.
    This walker concatenates text nodes with paragraph-respecting newlines —
    loses tables/code-block fidelity but renders readable prose for the
    detail page. Upgrade path: call Jira with ?expand=renderedFields for
    server-rendered HTML, or add a proper ADF renderer frontend-side.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_adf_to_text(n) for n in node)
    if not isinstance(node, dict):
        return ""
    t = node.get("type")
    out = ""
    if t == "text":
        out = node.get("text") or ""
    else:
        out = _adf_to_text(node.get("content"))
    if t in {"paragraph", "heading", "bulletList", "orderedList", "listItem", "codeBlock"}:
        out += "\n"
    return out


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


@router.get("/tickets/{key}", response_model=TicketDetailResponse)
async def get_ticket(
    key: str,
    ctx: TenantContext = Depends(resolve_tenant),
    _user: User = Depends(require_authenticated),
):
    """Get a single ticket by key. Within a tenant, Jira issue keys are
    globally unique across any jira_sites rows (Atlassian namespaces by
    project prefix), so we don't need a site_id in the URL.

    Returns issue metadata + description (flattened from ADF) + comments
    (empty today — the worker doesn't sync comments yet; schema is
    ready for when it does).
    """
    stmt = select(JiraIssue).where(JiraIssue.key == key)
    row = (await ctx.session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    fields: dict[str, Any] = (row.raw or {}).get("fields") or {}
    description = _adf_to_text(fields.get("description")).strip() or None

    # Prefer the jira_comments table when the worker has populated it (Phase 2
    # expand). In Phase 1 the table is empty but raw.fields.comment.comments
    # holds the first ~5 comments inline from the /search/jql response — parse
    # those so detail pages render immediately.
    comments_rows = (
        await ctx.session.execute(
            select(JiraComment)
            .where(JiraComment.site_id == row.site_id, JiraComment.issue_key == key)
            .order_by(JiraComment.created.asc())
        )
    ).scalars().all()
    if comments_rows:
        comments = [CommentResponse.model_validate(c) for c in comments_rows]
    else:
        comments = []
        raw_comments = ((fields.get("comment") or {}).get("comments")) or []
        for c in raw_comments:
            author = (c.get("author") or {}).get("emailAddress") or (c.get("author") or {}).get("displayName")
            body_text = _adf_to_text(c.get("body")).strip()
            created = c.get("created")
            if not created:
                continue
            # Synthesize an int id from the Jira comment id for the schema's
            # int id field. Jira ids are numeric-ish strings, try int cast;
            # fall back to hash if not.
            raw_id = c.get("id") or "0"
            try:
                cid = int(raw_id)
            except (TypeError, ValueError):
                cid = abs(hash(raw_id)) & 0x7FFFFFFF
            from datetime import datetime as _dt
            created_dt = _dt.fromisoformat(created.replace("Z", "+00:00"))
            comments.append(CommentResponse(
                id=cid,
                author=author,
                body=body_text or "(empty)",
                created=created_dt,
            ))

    return TicketDetailResponse.model_validate(row).model_copy(
        update={"description": description, "comments": comments}
    )
