"""Tenant-management CLI.

Usage:
    python -m lens.cli.tenants add topbuild --name "TopBuild, Inc." --color "#ff6a00"
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from lens.config import settings
from lens.db.engine import get_engine
from lens.logging import configure_logging, get_logger
from lens.models.core.sync_state import SyncState
from lens.models.core.tenants import Tenant

configure_logging()
log = get_logger("lens.cli.tenants")

ENABLED_SOURCES = ["jira"]  # Phase 1


async def _add_tenant(slug: str, name: str, color: str | None) -> int:
    schema_name = f"portal_{slug}"
    engine = get_engine()

    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        existing = (
            await session.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if existing is None:
            tenant = Tenant(slug=slug, name=name, schema_name=schema_name, color_hex=color)
            session.add(tenant)
            await session.flush()
            log.info("tenant_created", slug=slug, name=name)
        else:
            tenant = existing
            log.info("tenant_already_exists", slug=slug)

        # Seed sync_state rows for enabled sources (idempotent).
        for source in ENABLED_SOURCES:
            exists = (
                await session.execute(
                    select(SyncState).where(
                        SyncState.tenant_id == tenant.id, SyncState.source == source
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(SyncState(tenant_id=tenant.id, source=source, mode="backfill"))
        await session.commit()

    # Run tenant migrations. Invoke `alembic` via subprocess — same approach as
    # the billing app's deploy script — so env.py's -x handling is unambiguous.
    log.info("alembic_tenant_upgrade", slug=slug)
    cmd = ["alembic", "-x", f"mode=tenant:{slug}", "upgrade", "head"]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        log.error("alembic_tenant_upgrade_failed", slug=slug, rc=result.returncode)
        return result.returncode

    log.info("tenant_ready", slug=slug, schema=schema_name)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Lens tenant management")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="Create a new tenant")
    add.add_argument("slug")
    add.add_argument("--name", required=True)
    add.add_argument("--color", default=None)

    args = parser.parse_args()
    if args.cmd == "add":
        rc = asyncio.run(_add_tenant(args.slug, args.name, args.color))
        sys.exit(rc)


if __name__ == "__main__":
    main()
