"""Jira sync worker.

Run:
    python -m lens.workers.jira --interval 60
    python -m lens.workers.jira --tenant topbuild --mode backfill

Phase 1 scope:
- Loop over all tenants with a sync_state row for source='jira'.
- On first run for a tenant (no sync_state row yet), start in 'backfill'.
- Dual-write raw jira_issues + lens_core.activities in one transaction,
  using ON CONFLICT (dedup_key) DO NOTHING for idempotency.
- Log via structlog.
- Gracefully skip tenants whose Jira secret isn't configured.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lens.db.engine import get_tenant_engine
from lens.db.session import get_db  # noqa: F401 (for parity)
from lens.logging import configure_logging, get_logger
from lens.models.core.sync_state import SyncState
from lens.models.core.tenants import Tenant
from lens.services.activities import record_activity
from lens.services.jira import JiraClient
from lens.services.jira_tenant import (
    ensure_site as _ensure_site,
)
from lens.services.jira_tenant import (
    resolve_jira_config as _resolve_jira_config,
)
from lens.services.jira_tenant import (
    upsert_issue as _upsert_issue,
)

# Re-exports so the worker's public symbol names keep working for any external
# importers (tests, ops scripts) that already reference `_resolve_jira_config`
# or `_upsert_issue` via `lens.workers.jira`.
__all__ = ["_resolve_jira_config", "_upsert_issue", "_ensure_site"]

configure_logging()
log = get_logger("lens.worker.jira")


async def _tenant_session(tenant: Tenant) -> AsyncSession:
    engine = get_tenant_engine(tenant.db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    # Apply schema_translate_map at connection checkout.
    await session.connection(
        execution_options={"schema_translate_map": {"tenant": tenant.schema_name}}
    )
    return session


async def sync_tenant(
    tenant: Tenant,
    mode_override: str | None = None,
) -> None:
    cfg = _resolve_jira_config(tenant.slug)
    if cfg is None:
        log.info("jira_skip_tenant_no_creds", tenant=tenant.slug)
        return
    base_url, authorization = cfg

    session = await _tenant_session(tenant)
    started = datetime.now(UTC)
    try:
        # Load or create sync_state
        ss = (
            await session.execute(
                select(SyncState).where(
                    SyncState.tenant_id == tenant.id, SyncState.source == "jira"
                )
            )
        ).scalar_one_or_none()
        if ss is None:
            ss = SyncState(tenant_id=tenant.id, source="jira", mode="backfill")
            session.add(ss)
            await session.flush()

        mode = mode_override or ss.mode or "incremental"

        site = await _ensure_site(session, base_url)

        # Atlassian's new /search/jql endpoint rejects unbounded queries with
        # "Unbounded JQL queries are not allowed here." — we always restrict
        # to tickets assigned to the auth'd user (matches DESIGN §1: Lens
        # shows "my tickets"). On incremental passes we also bound by updated.
        jql_parts = ["assignee = currentUser()"]
        if mode == "incremental" and ss.cursor:
            # 5-min overlap per Teo §10
            jql_parts.append(f'updated >= "{_format_jql_datetime(ss.cursor)}"')
        jql = " AND ".join(jql_parts) + " ORDER BY updated ASC"

        async with JiraClient(base_url, authorization) as client:
            page = await client.search_issues(
                jql=jql,
                fields=[
                    "summary",
                    "status",
                    "priority",
                    "assignee",
                    "reporter",
                    "created",
                    "updated",
                    # Fetched for the detail page — ADF JSON; we flatten to
                    # text at render time via lens.routers.tickets._adf_to_text.
                    "description",
                    # Inline comments — Jira caps this at 5 per issue; for full
                    # coverage we'll later pull /rest/api/3/issue/{key}/comment
                    # separately. Phase 1: show the first 5 on detail pages.
                    "comment",
                ],
                max_results=100,
            )

        issues = page.get("issues", [])
        log.info("jira_sync_page", tenant=tenant.slug, mode=mode, count=len(issues))

        max_updated: datetime | None = None
        for issue in issues:
            await _upsert_issue(session, site.id, issue)
            fields = issue.get("fields", {}) or {}
            updated_ts = fields.get("updated")
            if updated_ts:
                try:
                    updated_dt = datetime.fromisoformat(updated_ts.replace("Z", "+00:00"))
                except ValueError:
                    updated_dt = None
                if updated_dt and (max_updated is None or updated_dt > max_updated):
                    max_updated = updated_dt

            # Activity row for incremental changes only (backfill suppresses per Teo §10)
            if mode == "incremental":
                await record_activity(
                    session,
                    tenant_id=tenant.id,
                    source="jira",
                    dedup_key=f"{issue['key']}:updated:{updated_ts}",
                    actor=(fields.get("assignee") or {}).get("emailAddress") or "system",
                    action="issue_updated",
                    subject=fields.get("summary") or issue["key"],
                    occurred_at=_safe_parse(updated_ts) or started,
                    metadata={"key": issue["key"], "status": (fields.get("status") or {}).get("name")},
                )

        # Advance cursor
        if max_updated is not None:
            ss.cursor = max_updated.isoformat()
        ss.last_run_at = started
        ss.last_success_at = started
        ss.last_error = None

        # Transition backfill → incremental when the first page is fully consumed.
        # Phase 1: single-page; Phase 2 will paginate. Mark backfill complete if
        # we got fewer than max_results back.
        if mode == "backfill" and len(issues) < 100:
            ss.backfill_complete_at = started
            ss.mode = "incremental"

        await session.commit()
        log.info("jira_sync_ok", tenant=tenant.slug, mode=mode, cursor=ss.cursor)
    except Exception as e:  # noqa: BLE001 — surface to sync_state
        await session.rollback()
        # Write the error on a fresh session so the rollback doesn't eat it.
        async with async_sessionmaker(get_tenant_engine(tenant.db_url), expire_on_commit=False)() as s2:
            await s2.connection(
                execution_options={"schema_translate_map": {"tenant": tenant.schema_name}}
            )
            stmt = pg_insert(SyncState).values(
                tenant_id=tenant.id,
                source="jira",
                mode="backfill",
                last_run_at=started,
                last_error=str(e)[:4000],
            ).on_conflict_do_update(
                index_elements=["tenant_id", "source"],
                set_={"last_run_at": started, "last_error": str(e)[:4000]},
            )
            await s2.execute(stmt)
            await s2.commit()
        log.error("jira_sync_fail", tenant=tenant.slug, error=str(e))
    finally:
        await session.close()


def _format_jql_datetime(ts: str) -> str:
    """Format an ISO-8601 timestamp for JQL's `updated >= "..."` clause.

    JQL only accepts `"yyyy-MM-dd HH:mm"` (minute precision, no seconds, no
    fractional, no timezone offset). Passing anything else — including the
    full ISO-8601 form Postgres stores — makes Atlassian silently return zero
    matches, freezing the sync cursor. Always normalize to UTC minute
    precision before it goes on the wire.
    """
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def _safe_parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


async def list_tenants_for_sync(slug_filter: str | None) -> list[Tenant]:
    from lens.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as s:
        stmt = select(Tenant).where(Tenant.archived_at.is_(None))
        if slug_filter:
            stmt = stmt.where(Tenant.slug == slug_filter)
        return list((await s.execute(stmt)).scalars().all())


async def run_loop(interval: int, slug_filter: str | None, mode_override: str | None) -> None:
    while True:
        tenants = await list_tenants_for_sync(slug_filter)
        log.info("jira_worker_tick", tenant_count=len(tenants))
        for t in tenants:
            try:
                await sync_tenant(t, mode_override=mode_override)
            except Exception as e:  # noqa: BLE001
                log.error("jira_worker_tenant_error", tenant=t.slug, error=str(e))
        await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lens — Jira sync worker")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between sync passes")
    parser.add_argument("--tenant", type=str, default=None, help="Only sync this tenant slug")
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=["backfill", "incremental"],
        help="Force mode (default: follow sync_state.mode)",
    )
    args = parser.parse_args()
    log.info("jira_worker_start", interval=args.interval, tenant=args.tenant, mode=args.mode)
    try:
        asyncio.run(run_loop(args.interval, args.tenant, args.mode))
    except KeyboardInterrupt:
        log.info("jira_worker_stop")


if __name__ == "__main__":
    main()
