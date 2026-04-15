"""Seed dev data: TopBuild tenant + Steve user + user_tenants grant.

Idempotent. Called from docker-compose.dev.yml at every backend startup.
"""

from __future__ import annotations

import asyncio
import subprocess

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from lens.config import settings
from lens.db.engine import get_engine
from lens.logging import configure_logging, get_logger
from lens.models.core.sync_state import SyncState
from lens.models.core.tenants import Tenant
from lens.models.core.user_tenants import UserTenant
from lens.models.core.users import User

configure_logging()
log = get_logger("lens.cli.seed_dev")


TOPBUILD = {"slug": "topbuild", "name": "TopBuild, Inc.", "color": "#ff6a00"}


async def _seed() -> None:
    engine = get_engine()

    # Ensure schema exists before migrations run.
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "lens_{TOPBUILD["slug"]}"'))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # Tenant
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == TOPBUILD["slug"]))
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(
                slug=TOPBUILD["slug"],
                name=TOPBUILD["name"],
                schema_name=f"lens_{TOPBUILD['slug']}",
                color_hex=TOPBUILD["color"],
            )
            session.add(tenant)
            await session.flush()
            log.info("seed_tenant_created", slug=tenant.slug)
        else:
            log.info("seed_tenant_exists", slug=tenant.slug)

        # User
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

        # Grant
        access = (
            await session.execute(
                select(UserTenant).where(
                    UserTenant.user_id == user.id, UserTenant.tenant_id == tenant.id
                )
            )
        ).scalar_one_or_none()
        if access is None:
            session.add(UserTenant(user_id=user.id, tenant_id=tenant.id, role="owner"))
            log.info("seed_grant_created", email=email, tenant=tenant.slug)
        else:
            log.info("seed_grant_exists", email=email, tenant=tenant.slug)

        # Sync state row for jira (idempotent).
        ss = (
            await session.execute(
                select(SyncState).where(
                    SyncState.tenant_id == tenant.id, SyncState.source == "jira"
                )
            )
        ).scalar_one_or_none()
        if ss is None:
            session.add(SyncState(tenant_id=tenant.id, source="jira", mode="backfill"))
            log.info("seed_sync_state_created", tenant=tenant.slug, source="jira")

        await session.commit()

    # Ensure tenant migrations are at head. The compose command runs
    # `alembic -x mode=all upgrade head` before us, but this makes seed_dev
    # safe to call standalone too.
    cmd = ["alembic", "-x", f"mode=tenant:{TOPBUILD['slug']}", "upgrade", "head"]
    subprocess.run(cmd, check=False)

    log.info("seed_complete")


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
