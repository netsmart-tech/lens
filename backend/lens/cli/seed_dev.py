"""Seed dev data: Entourage + Eminem tenants, Steve user, themed fake Jira issues.

Idempotent. Called from docker-compose.dev.yml at every backend startup.

Tenants are deliberately fictional so no dev ever mistakes seed data for a
real client. Themed issues give the ticketing UI a realistic spread across
every status and priority for exercising filters, sorts, and detail views.
"""

from __future__ import annotations

import asyncio
import subprocess
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lens.config import settings
from lens.db.engine import get_engine
from lens.logging import configure_logging, get_logger
from lens.models.core.sync_state import SyncState
from lens.models.core.tenants import Tenant
from lens.models.core.user_tenants import UserTenant
from lens.models.core.users import User
from lens.models.tenant.jira_issues import JiraIssue
from lens.models.tenant.jira_sites import JiraSite

configure_logging()
log = get_logger("lens.cli.seed_dev")


# (summary, status, priority, assignee) — assignee may be None.
ENTOURAGE_ISSUES: list[tuple[str, str, str, str | None]] = [
    ("Book Vince for Medellin sequel read-through", "In Progress", "High", "Eric Murphy"),
    ("Hug it out with Dana Gordon re: Gatsby role", "Blocked", "Highest", "Ari Gold"),
    ("Turtle's tequila pitch deck — Avión round two", "To Do", "Low", "Turtle"),
    ("Johnny Drama's Five Towns reboot audition tape", "To Do", "Medium", "Johnny Drama"),
    ("Close the Aquaman deal with Warner Bros", "Done", "Highest", "Ari Gold"),
    ("Get Lloyd that promotion (finally)", "Done", "Medium", "Ari Gold"),
    ("Fire the PR team. Again.", "In Progress", "High", "Shauna"),
    ("Sign Billy Walsh to direct Queens Boulevard 2", "In Review", "Highest", "Vincent Chase"),
    ("Rent Malibu beach house for the summer", "To Do", "Lowest", "Turtle"),
    ("Viking Quest residuals audit", "Blocked", "Medium", "Johnny Drama"),
    ("Pitch Queens Boulevard franchise to studios", "In Progress", "High", "Eric Murphy"),
    ("Handle TMZ scandal fallout (again)", "In Progress", "Highest", "Shauna"),
    ("Settle Turtle's limo-company invoice dispute", "Done", "Low", "Turtle"),
    ("Cast reunion dinner at Koi — book the back room", "Done", "Lowest", "Eric Murphy"),
    ("Mrs. Ari's anger-management refresher (for Ari)", "To Do", "High", "Ari Gold"),
    ("Find Drama a new stylist. Immediately.", "In Review", "Low", "Johnny Drama"),
    ("Review Medellin box-office actuals vs pro-forma", "Done", "Medium", "Eric Murphy"),
    ("Negotiate new Warner Bros first-look deal", "In Review", "Medium", "Eric Murphy"),
    ("Book Kanye for soundtrack EP cameo", "To Do", "Medium", "Vincent Chase"),
    ("Replace Turtle's '66 Lincoln — engine shot", "To Do", "Low", None),
    ("Ari's court-ordered anger management session", "Blocked", "Highest", "Ari Gold"),
]

EMINEM_ISSUES: list[tuple[str, str, str, str | None]] = [
    ("Master final mix for Curtain Call 2 reissue", "In Progress", "Highest", "Dr. Dre"),
    ("Shady Records A&R — Q2 demo submissions review", "In Review", "Medium", "Paul Rosenberg"),
    ("Settle beef with Machine Gun Kelly (publicly)", "Blocked", "High", "Marshall Mathers"),
    ("8 Mile 20th-anniversary theatrical re-release", "To Do", "Low", "Paul Rosenberg"),
    ("Clear Dido 'Thank You' sample for Stan remaster", "Blocked", "Medium", None),
    ("Prep Dre for Coachella surprise-guest verse", "In Progress", "High", "Marshall Mathers"),
    ("Final cut review — Stan Netflix documentary", "To Do", "Medium", "Paul Rosenberg"),
    ("Process G-Unit royalty split (Q3 FY26)", "Done", "Highest", "Paul Rosenberg"),
    ("Tour bus transmission repair — Detroit leg", "Done", "Low", None),
    ("Order new SM7B mics for Studio A", "To Do", "Lowest", None),
    ("Record verse for Detox (still?)", "In Progress", "High", "Marshall Mathers"),
    ("Approve Proof tribute merch final designs", "In Review", "Medium", "Marshall Mathers"),
    ("Lock in SNL November performance slot", "To Do", "High", "Paul Rosenberg"),
    ("Shelter freestyle night — confirm surprise drop-in", "Done", "Medium", "Marshall Mathers"),
    ("Wipe old Sidekick from the Benzino era", "Done", "Lowest", "Marshall Mathers"),
    ("Draft response to latest ghostwriter allegations", "Blocked", "Highest", None),
    ("Finalize Music To Be Murdered By Pt. 3 tracklist", "In Review", "High", "Marshall Mathers"),
    ("Counter Nick Cannon's latest diss track", "To Do", "Medium", "Marshall Mathers"),
    ("Rent Gilbert's Lodge for album listening party", "To Do", "Lowest", "Paul Rosenberg"),
    ("Submit Lose Yourself for Songwriters Hall of Fame", "In Progress", "Low", "Paul Rosenberg"),
    ("Finalize verse for Dre x 50 Cent reunion track", "To Do", "High", "Marshall Mathers"),
]

TENANTS: list[dict] = [
    {
        "slug": "entourage",
        "name": "Entourage Ent., LLC",
        "color": "#C8102E",
        "key_prefix": "ENT",
        "site_base_url": "https://entourage-hq.atlassian.net",
        "site_display_name": "Entourage HQ",
        "issues": ENTOURAGE_ISSUES,
    },
    {
        "slug": "eminem",
        "name": "Shady Records",
        "color": "#5A0000",
        "key_prefix": "SHDY",
        "site_base_url": "https://shady-records.atlassian.net",
        "site_display_name": "Shady Records",
        "issues": EMINEM_ISSUES,
    },
]


def _issue_timestamps(index: int, total: int, now: datetime) -> tuple[datetime, datetime]:
    """Spread updates linearly from ~1h ago to ~90d ago; created a week before updated."""
    span = timedelta(days=90) - timedelta(hours=1)
    updated = now - timedelta(hours=1) - span * (index / max(total - 1, 1))
    created = updated - timedelta(days=7)
    return created, updated


async def _seed_issues(
    session: AsyncSession,
    site_id: uuid.UUID,
    key_prefix: str,
    issues: list[tuple[str, str, str, str | None]],
    tenant_slug: str,
) -> None:
    existing = await session.scalar(
        select(func.count()).select_from(JiraIssue).where(JiraIssue.site_id == site_id)
    )
    if existing:
        log.info("seed_issues_skip", tenant=tenant_slug, count=existing)
        return

    now = datetime.now(UTC)
    for i, (summary, status, priority, assignee) in enumerate(issues, start=1):
        created, updated = _issue_timestamps(i - 1, len(issues), now)
        session.add(
            JiraIssue(
                site_id=site_id,
                key=f"{key_prefix}-{i}",
                summary=summary,
                status=status,
                priority=priority,
                assignee=assignee,
                reporter=assignee,
                issue_created=created,
                issue_updated=updated,
            )
        )
    log.info("seed_issues_created", tenant=tenant_slug, count=len(issues))


async def _seed_tenant(spec: dict, user_id: uuid.UUID) -> None:
    slug = spec["slug"]
    schema_name = f"lens_{slug}"
    engine = get_engine()

    # 1. Core schema + tenant row + user grant + sync_state (default factory, no translate map).
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(
                slug=slug,
                name=spec["name"],
                schema_name=schema_name,
                color_hex=spec["color"],
            )
            session.add(tenant)
            await session.flush()
            log.info("seed_tenant_created", slug=slug)
        else:
            log.info("seed_tenant_exists", slug=slug)

        grant = (
            await session.execute(
                select(UserTenant).where(
                    UserTenant.user_id == user_id, UserTenant.tenant_id == tenant.id
                )
            )
        ).scalar_one_or_none()
        if grant is None:
            session.add(UserTenant(user_id=user_id, tenant_id=tenant.id, role="owner"))
            log.info("seed_grant_created", slug=slug)

        if not await session.scalar(
            select(SyncState).where(
                SyncState.tenant_id == tenant.id, SyncState.source == "jira"
            )
        ):
            session.add(SyncState(tenant_id=tenant.id, source="jira", mode="backfill"))
            log.info("seed_sync_state_created", slug=slug)

        await session.commit()

    # 2. Run tenant migrations so jira_sites/jira_issues exist in this tenant's schema.
    subprocess.run(
        ["alembic", "-x", f"mode=tenant:{slug}", "upgrade", "head"], check=False
    )

    # 3. Tenant-scoped session via schema_translate_map for jira_sites + jira_issues.
    async with factory() as session:
        await session.connection(
            execution_options={"schema_translate_map": {"tenant": schema_name}}
        )

        site = (
            await session.execute(
                select(JiraSite).where(JiraSite.base_url == spec["site_base_url"])
            )
        ).scalar_one_or_none()
        if site is None:
            site = JiraSite(
                base_url=spec["site_base_url"],
                display_name=spec["site_display_name"],
            )
            session.add(site)
            await session.flush()
            log.info("seed_site_created", slug=slug, display_name=site.display_name)

        await _seed_issues(session, site.id, spec["key_prefix"], spec["issues"], slug)
        await session.commit()


async def _seed_user() -> uuid.UUID:
    engine = get_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        email = settings.lens_dev_user_email
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                display_name=settings.lens_dev_user_name,
                is_staff=True,
            )
            session.add(user)
            await session.flush()
            log.info("seed_user_created", email=email)
        else:
            log.info("seed_user_exists", email=email)
        await session.commit()
        return user.id


async def _seed() -> None:
    user_id = await _seed_user()
    for spec in TENANTS:
        await _seed_tenant(spec, user_id)
    log.info("seed_complete")


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
