"""Alembic environment — supports three invocation modes via `-x mode=...`.

    -x mode=core               migrate portal_core schema
    -x mode=tenant:<slug>      migrate one tenant schema (portal_<slug>)
    -x mode=all                core first, then every registered tenant

Each tenant carries its own `alembic_version` table inside its own schema
(version_table_schema=<tenant schema>) so tenants can sit at different heads.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure our models are imported so Base.metadata is populated.
import lens.models  # noqa: F401
from lens.db.base import CoreBase, TenantBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def _get_mode() -> str:
    x = context.get_x_argument(as_dictionary=True)
    return x.get("mode", "core")


def _is_tenant_migration(revision) -> bool:
    """Helper for migration scripts: returns True if current mode is a tenant migration."""
    return _get_mode().startswith("tenant:")


def _tenant_slug() -> str | None:
    mode = _get_mode()
    if mode.startswith("tenant:"):
        return mode.split(":", 1)[1]
    return None


def _do_run_migrations_core(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=CoreBase.metadata,
        version_table="alembic_version",
        version_table_schema="portal_core",
        include_schemas=True,
        include_object=_include_core_only,
    )
    # Migrations read this to phase-guard their upgrade()/downgrade() —
    # `include_object` only filters autogenerate, not manual op.create_table calls.
    context.config.attributes["phase"] = "core"
    context.config.attributes["tenant_slug"] = None
    with context.begin_transaction():
        # Ensure schema exists inside the transaction so it commits with the rest.
        connection.execute(text('CREATE SCHEMA IF NOT EXISTS "portal_core"'))
        context.run_migrations()


def _include_core_only(obj, name, type_, reflected, compare_to):
    # Only emit DDL for portal_core.* tables in core mode.
    if type_ == "table":
        return obj.schema == "portal_core"
    return True


def _do_run_migrations_tenant(connection, slug: str) -> None:
    schema = f"portal_{slug}"
    connection = connection.execution_options(
        schema_translate_map={"tenant": schema, None: schema}
    )
    context.configure(
        connection=connection,
        target_metadata=TenantBase.metadata,
        version_table="alembic_version",
        version_table_schema=schema,
        include_schemas=True,
    )
    context.config.attributes["phase"] = "tenant"
    context.config.attributes["tenant_slug"] = slug
    with context.begin_transaction():
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        context.run_migrations()


async def _run_async(runner) -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(runner)
        # Alembic's begin_transaction() issues COMMIT at the sync layer, but the
        # async wrapper doesn't auto-flush it — commit explicitly here so DDL
        # actually persists. Without this the migrations appear to run and
        # then silently roll back on connection close.
        await connection.commit()
    await connectable.dispose()


async def _run_all() -> None:
    # First: core. Then: every tenant.
    await _run_async(_do_run_migrations_core)

    # Discover tenants from portal_core.tenants. If the table doesn't exist
    # yet (fresh DB + mode=all), core migrations just created it so this works.
    from sqlalchemy import select

    from lens.models.core.tenants import Tenant

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    try:
        async with connectable.connect() as conn:
            result = await conn.execute(select(Tenant.slug).where(Tenant.archived_at.is_(None)))
            slugs = [r[0] for r in result]
    finally:
        await connectable.dispose()

    for slug in slugs:
        await _run_async(lambda c, s=slug: _do_run_migrations_tenant(c, s))


def run_migrations_online() -> None:
    mode = _get_mode()
    if mode == "core":
        asyncio.run(_run_async(_do_run_migrations_core))
    elif mode.startswith("tenant:"):
        slug = mode.split(":", 1)[1]
        asyncio.run(_run_async(lambda c: _do_run_migrations_tenant(c, slug)))
    elif mode == "all":
        asyncio.run(_run_all())
    else:
        raise ValueError(f"Unknown alembic mode: {mode!r}")


def run_migrations_offline() -> None:
    raise NotImplementedError("Lens requires online migrations (schema-per-tenant).")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
