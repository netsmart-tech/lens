"""Jira sync worker.

Run:
    python -m lens.workers.jira --interval 60
    python -m lens.workers.jira --tenant topbuild --mode backfill

Phase 1 scope:
- Loop over all tenants with a sync_state row for source='jira'.
- On first run for a tenant (no sync_state row yet), start in 'backfill'.
- Dual-write raw jira_issues + portal_core.activities in one transaction,
  using ON CONFLICT (dedup_key) DO NOTHING for idempotency.
- Log via structlog.
- Gracefully skip tenants whose Jira secret isn't configured.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lens.config import settings
from lens.db.engine import get_tenant_engine
from lens.db.session import get_db  # noqa: F401 (for parity)
from lens.logging import configure_logging, get_logger
from lens.models.core.sync_state import SyncState
from lens.models.core.tenants import Tenant
from lens.models.tenant.jira_issues import JiraIssue
from lens.models.tenant.jira_sites import JiraSite
from lens.services.activities import record_activity
from lens.services.jira import JiraClient
from lens.services.secrets_proxy import get_secret

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


async def _resolve_jira_credentials(slug: str) -> tuple[str, str, str] | None:
    """Return (base_url, email, token) or None if unconfigured.

    Tries three named secrets per tenant slug:
      <slug>-jira-url, <slug>-jira-email, <slug>-jira-api-token
    """
    try:
        base_url = await get_secret(f"{slug}-jira-url")
        email = await get_secret(f"{slug}-jira-email")
        token = await get_secret(f"{slug}-jira-api-token")
    except (KeyError, NotImplementedError) as e:
        log.info("jira_creds_unavailable", tenant=slug, reason=str(e))
        return None
    return base_url, email, token


async def _ensure_site(session: AsyncSession, base_url: str) -> JiraSite:
    stmt = select(JiraSite).where(JiraSite.base_url == base_url)
    site = (await session.execute(stmt)).scalar_one_or_none()
    if site is None:
        site = JiraSite(base_url=base_url, display_name=base_url)
        session.add(site)
        await session.flush()
    return site


async def _upsert_issue(session: AsyncSession, site_id: uuid.UUID, issue: dict) -> None:
    fields = issue.get("fields", {}) or {}
    assignee = (fields.get("assignee") or {}).get("emailAddress")
    reporter = (fields.get("reporter") or {}).get("emailAddress")
    status_name = (fields.get("status") or {}).get("name")
    priority = (fields.get("priority") or {}).get("name")

    def _parse(ts: str | None) -> datetime | None:
        if not ts:
            return None
        # Jira returns '2026-04-15T12:34:56.789+0000' — fromisoformat handles most variants in 3.11+
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None

    values = {
        "site_id": site_id,
        "key": issue["key"],
        "summary": fields.get("summary") or "",
        "status": status_name,
        "priority": priority,
        "assignee": assignee,
        "reporter": reporter,
        "issue_created": _parse(fields.get("created")),
        "issue_updated": _parse(fields.get("updated")),
        "raw": issue,
        "synced_at": datetime.now(UTC),
    }
    stmt = pg_insert(JiraIssue).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["site_id", "key"],
        set_={k: stmt.excluded[k] for k in values if k not in ("site_id", "key")},
    )
    await session.execute(stmt)


async def sync_tenant(
    tenant: Tenant,
    mode_override: str | None = None,
) -> None:
    creds = await _resolve_jira_credentials(tenant.slug)
    if creds is None:
        log.info("jira_skip_tenant_no_creds", tenant=tenant.slug)
        return
    base_url, email, token = creds

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

        jql_parts = []
        if mode == "incremental" and ss.cursor:
            # 5-min overlap per Teo §10
            jql_parts.append(f'updated >= "{ss.cursor}"')
        jql = " AND ".join(jql_parts) + (" ORDER BY updated ASC" if jql_parts else "ORDER BY updated ASC")

        async with JiraClient(base_url, email, token) as client:
            page = await client.search_issues(
                jql=jql,
                fields=["summary", "status", "priority", "assignee", "reporter", "created", "updated"],
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
