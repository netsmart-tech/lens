"""Tenant-scoped Jira helpers shared by the sync worker and the tickets router.

Two things live here:

1. `resolve_jira_config(slug)` — returns `(base_url, authorization_header)` for a
   given tenant, honoring the secrets-proxy placeholder pattern in prod and
   the dev-fallback env vars (`LENS_STATIC_<SLUG>_JIRA_EMAIL` / `_TOKEN`) when
   no proxy is configured. Originally lived in `workers/jira.py`; hoisted here
   so the mutation endpoints in `routers/tickets.py` can use the same lookup.

2. `upsert_issue(session, site_id, issue)` — upserts one Jira issue (as
   returned by `/rest/api/3/issue/{key}` or `/search/jql`) into the tenant's
   `jira_issues` table. Originally the private `_upsert_issue` in the worker;
   hoisted here so the transition endpoint can re-sync an issue after Jira
   applies the status change without reinventing the mapping.

`workers/jira.py` re-exports these names to preserve its old import surface.
"""

from __future__ import annotations

import base64
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lens.config import settings
from lens.logging import get_logger
from lens.models.tenant.jira_issues import JiraIssue
from lens.models.tenant.jira_sites import JiraSite

log = get_logger(__name__)


def resolve_jira_config(slug: str) -> tuple[str, str] | None:
    """Return (base_url, authorization_header) or None if unconfigured.

    Per-tenant config:
      - `JIRA_<SLUG>_URL` (env var, sourced from Infisical /apps/lens/) — required.
      - In prod (secrets_proxy_url set): authorization is the literal placeholder
        ``Basic {secret:<slug>-jira-api-token}``. The proxy substitutes the stored
        base64(email:token) blob before forwarding to Atlassian.
      - In dev (no proxy): authorization is constructed locally from
        ``LENS_STATIC_<SLUG>_JIRA_EMAIL`` + ``LENS_STATIC_<SLUG>_JIRA_TOKEN``.
    """
    slug_env = slug.upper().replace("-", "_")
    base_url = os.environ.get(f"JIRA_{slug_env}_URL")
    if not base_url:
        log.info("jira_skip_no_url", tenant=slug, env_var=f"JIRA_{slug_env}_URL")
        return None

    if settings.secrets_proxy_url:
        authorization = f"Basic {{secret:{slug}-jira-api-token}}"
    else:
        email = os.environ.get(f"LENS_STATIC_{slug_env}_JIRA_EMAIL")
        token = os.environ.get(f"LENS_STATIC_{slug_env}_JIRA_TOKEN")
        if not (email and token):
            log.info("jira_skip_no_dev_creds", tenant=slug)
            return None
        encoded = base64.b64encode(f"{email}:{token}".encode()).decode()
        authorization = f"Basic {encoded}"

    return base_url, authorization


async def ensure_site(session: AsyncSession, base_url: str) -> JiraSite:
    """Fetch or lazily create the `jira_sites` row for this Jira base URL."""
    stmt = select(JiraSite).where(JiraSite.base_url == base_url)
    site = (await session.execute(stmt)).scalar_one_or_none()
    if site is None:
        site = JiraSite(base_url=base_url, display_name=base_url)
        session.add(site)
        await session.flush()
    return site


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


async def upsert_issue(session: AsyncSession, site_id: uuid.UUID, issue: dict) -> None:
    """Upsert one Jira issue payload into `tenant.jira_issues`.

    Caller is responsible for commit. Payload shape matches Jira's
    `/rest/api/3/issue/{key}` response (or per-issue entries from `/search/jql`).
    """
    fields = issue.get("fields", {}) or {}
    assignee = (fields.get("assignee") or {}).get("emailAddress")
    reporter = (fields.get("reporter") or {}).get("emailAddress")
    status_name = (fields.get("status") or {}).get("name")
    priority = (fields.get("priority") or {}).get("name")

    values = {
        "site_id": site_id,
        "key": issue["key"],
        "summary": fields.get("summary") or "",
        "status": status_name,
        "priority": priority,
        "assignee": assignee,
        "reporter": reporter,
        "issue_created": _parse_ts(fields.get("created")),
        "issue_updated": _parse_ts(fields.get("updated")),
        "raw": issue,
        "synced_at": datetime.now(UTC),
    }
    stmt = pg_insert(JiraIssue).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["site_id", "key"],
        set_={k: stmt.excluded[k] for k in values if k not in ("site_id", "key")},
    )
    await session.execute(stmt)
