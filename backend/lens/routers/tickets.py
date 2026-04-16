"""Tickets router — Jira issues for a given tenant."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lens.auth.deps import require_authenticated
from lens.db.tenant import TenantContext, resolve_tenant
from lens.logging import get_logger
from lens.models.core.users import User
from lens.models.tenant.jira_comments import JiraComment
from lens.models.tenant.jira_issues import JiraIssue
from lens.schemas.tickets import (
    CommentCreateRequest,
    CommentResponse,
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
    TransitionApplyRequest,
    TransitionListResponse,
    TransitionResponse,
)
from lens.services.jira import JiraClient, plain_text_to_adf
from lens.services.jira_tenant import ensure_site, resolve_jira_config, upsert_issue
from lens.services.sync_envelope import with_sync_envelope

log = get_logger(__name__)

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


async def _build_ticket_detail(
    row: JiraIssue, session: AsyncSession
) -> TicketDetailResponse:
    """Shape one `jira_issues` row into `TicketDetailResponse`.

    Centralizes the ADF-flatten + comments-from-raw-fallback so
    `GET /tickets/{key}`, `POST /tickets/{key}/transitions`, and
    `POST /tickets/{key}/refresh` all return the same shape. Prefers the
    `jira_comments` table when populated; falls back to the inline
    `raw.fields.comment.comments` when not.
    """
    fields: dict[str, Any] = (row.raw or {}).get("fields") or {}
    description = _adf_to_text(fields.get("description")).strip() or None

    comments_rows = (
        await session.execute(
            select(JiraComment)
            .where(JiraComment.site_id == row.site_id, JiraComment.issue_key == row.key)
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
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            comments.append(CommentResponse(
                id=cid,
                author=author,
                body=body_text or "(empty)",
                created=created_dt,
            ))

    return TicketDetailResponse.model_validate(row).model_copy(
        update={"description": description, "comments": comments}
    )


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

    return await _build_ticket_detail(row, ctx.session)


# ---- mutations --------------------------------------------------------------


def _jira_client_for(slug: str) -> JiraClient:
    """Build a JiraClient for `slug`, or raise 503 if the tenant isn't configured.

    The router builds its own client per request (cheap — shared rate-limiter
    cache keyed by base_url), same pattern the sync worker uses. Lifetime is
    scoped to the request via `async with` in the endpoint body.
    """
    cfg = resolve_jira_config(slug)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Jira is not configured for tenant '{slug}'",
        )
    base_url, authorization = cfg
    return JiraClient(base_url, authorization)


def _raise_from_jira(e: httpx.HTTPStatusError) -> None:
    """Surface Jira's status + body to the caller. Never swallow."""
    body: Any
    try:
        body = e.response.json()
    except ValueError:
        body = e.response.text
    # Proxy Jira's status code through when it's a client error; map 5xx to 502.
    code = e.response.status_code
    if 400 <= code < 500:
        http_status = code
    else:
        http_status = status.HTTP_502_BAD_GATEWAY
    raise HTTPException(
        status_code=http_status,
        detail={"jira_status": code, "jira_body": body},
    ) from e


async def _load_issue_or_404(ctx: TenantContext, key: str) -> JiraIssue:
    row = (
        await ctx.session.execute(select(JiraIssue).where(JiraIssue.key == key))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return row


@router.post(
    "/tickets/{key}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    key: str,
    payload: CommentCreateRequest,
    ctx: TenantContext = Depends(resolve_tenant),
    _user: User = Depends(require_authenticated),
) -> CommentResponse:
    """Post a plain-text comment to a Jira issue and mirror it locally.

    Jira's POST returns the created comment in full; we flatten that back to
    our `CommentResponse` shape and ALSO upsert into `jira_comments` so the
    detail view sees it on next render without waiting for the 5-min worker
    pass. Dual-write note: once `jira_comments` has any row for an issue, the
    detail route stops falling back to `raw.fields.comment.comments`, so local
    rows become the source of truth for that issue. Phase 1 accepts that drift.
    """
    row = await _load_issue_or_404(ctx, key)

    adf = plain_text_to_adf(payload.body)
    async with _jira_client_for(ctx.tenant.slug) as client:
        try:
            created = await client.add_comment(key, adf)
        except httpx.HTTPStatusError as e:
            _raise_from_jira(e)

    # Flatten Jira's response into our CommentResponse shape.
    author_obj = created.get("author") or {}
    author = author_obj.get("emailAddress") or author_obj.get("displayName")
    body_text = _adf_to_text(created.get("body")).strip() or payload.body
    created_raw = created.get("created")
    created_dt: datetime
    if created_raw:
        try:
            created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            created_dt = datetime.now(UTC)
    else:
        created_dt = datetime.now(UTC)

    external_id = str(created.get("id") or "")
    try:
        int_id = int(external_id) if external_id else 0
    except ValueError:
        int_id = abs(hash(external_id)) & 0x7FFFFFFF

    # Dual-write: upsert into tenant.jira_comments so subsequent GETs surface it.
    if external_id:
        stmt = pg_insert(JiraComment).values(
            site_id=row.site_id,
            issue_key=key,
            external_id=external_id,
            author=author,
            body=body_text,
            created=created_dt,
        )
        # Unique identity for a comment within a tenant is (site_id, issue_key,
        # external_id); jira_comments has no explicit unique constraint on that
        # tuple today (id is autoincrement PK). Rather than add a migration for
        # Phase 1, we check-then-insert; a duplicate here is only possible if
        # Jira returned the same external_id twice within a transaction, which
        # it doesn't. If the next sync pass pulls the same comment, the
        # fallback-from-raw branch won't kick in (comments_rows is non-empty)
        # and the worker's Phase-2 dual-write will handle conflicts properly.
        existing = (
            await ctx.session.execute(
                select(JiraComment.id).where(
                    JiraComment.site_id == row.site_id,
                    JiraComment.issue_key == key,
                    JiraComment.external_id == external_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            await ctx.session.execute(stmt)

    return CommentResponse(
        id=int_id,
        author=author,
        body=body_text,
        created=created_dt,
    )


@router.get("/tickets/{key}/transitions", response_model=TransitionListResponse)
async def list_transitions(
    key: str,
    ctx: TenantContext = Depends(resolve_tenant),
    _user: User = Depends(require_authenticated),
) -> TransitionListResponse:
    """List workflow transitions available for this issue + user.

    Shape-maps Jira's `{transitions: [{id, name, to: {name}}]}` to our flatter
    `{transitions: [{id, name, to_status}]}`.
    """
    await _load_issue_or_404(ctx, key)

    async with _jira_client_for(ctx.tenant.slug) as client:
        try:
            raw = await client.list_transitions(key)
        except httpx.HTTPStatusError as e:
            _raise_from_jira(e)

    transitions = [
        TransitionResponse(
            id=str(t.get("id") or ""),
            name=t.get("name") or "",
            to_status=(t.get("to") or {}).get("name") or "",
        )
        for t in raw.get("transitions", [])
    ]
    return TransitionListResponse(transitions=transitions)


@router.post("/tickets/{key}/transitions", response_model=TicketDetailResponse)
async def apply_transition(
    key: str,
    payload: TransitionApplyRequest,
    ctx: TenantContext = Depends(resolve_tenant),
    _user: User = Depends(require_authenticated),
) -> TicketDetailResponse:
    """Apply a workflow transition, then re-sync the issue locally.

    Jira's POST /transitions returns 204; we immediately GET the issue back so
    our `jira_issues.status` reflects the change without waiting for the
    5-min worker pass, and return the refreshed `TicketDetailResponse`.
    """
    row = await _load_issue_or_404(ctx, key)

    async with _jira_client_for(ctx.tenant.slug) as client:
        try:
            await client.do_transition(key, payload.transition_id)
            refreshed = await client.get_issue(key)
        except httpx.HTTPStatusError as e:
            _raise_from_jira(e)

    await upsert_issue(ctx.session, row.site_id, refreshed)
    # The upsert goes through core SQL (pg_insert), not the ORM, so the
    # identity-mapped `row` from the earlier _load_issue_or_404 is stale.
    # Expire + re-select to pick up the new status/fields.
    ctx.session.expire(row)
    updated = (
        await ctx.session.execute(select(JiraIssue).where(JiraIssue.key == key))
    ).scalar_one()

    return await _build_ticket_detail(updated, ctx.session)


@router.post("/tickets/{key}/refresh", response_model=TicketDetailResponse)
async def refresh_ticket(
    key: str,
    ctx: TenantContext = Depends(resolve_tenant),
    _user: User = Depends(require_authenticated),
) -> TicketDetailResponse:
    """Force-resync a single ticket from Jira and return the refreshed detail.

    Bypasses the 5-min worker cadence so the detail page's refresh button
    reflects external Jira changes immediately. 404 if the ticket doesn't
    exist locally (refresh is a re-sync, not an import); 503 if the tenant
    isn't Jira-configured; Jira 4xx proxied through via `_raise_from_jira`.
    """
    row = await _load_issue_or_404(ctx, key)

    async with _jira_client_for(ctx.tenant.slug) as client:
        base_url = client.base_url
        try:
            # Match the fields the worker pulls so `raw` stays consistent between
            # worker syncs and ad-hoc refreshes. Jira's default field set already
            # includes description+comment, so this is belt-and-suspenders.
            issue_json = await client.get_issue(
                key,
                fields=[
                    "summary", "status", "priority", "assignee", "reporter",
                    "created", "updated", "description", "comment",
                ],
            )
        except httpx.HTTPStatusError as e:
            _raise_from_jira(e)

    # Re-ensure the site row keyed on base_url (cheap find-or-create — same
    # call shape as the worker). Matches whatever site the existing row points
    # at today since base_url is stable per-tenant.
    site = await ensure_site(ctx.session, base_url)
    await upsert_issue(ctx.session, site.id, issue_json)

    # upsert_issue uses core SQL (pg_insert), not the ORM, so the identity-mapped
    # `row` is stale — expire + re-select the same way apply_transition does.
    ctx.session.expire(row)
    updated = (
        await ctx.session.execute(select(JiraIssue).where(JiraIssue.key == key))
    ).scalar_one()

    return await _build_ticket_detail(updated, ctx.session)
