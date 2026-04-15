"""Shared test fixtures.

Per Teo §6 / DESIGN §5.2:
- Real Postgres via testcontainers (session-scoped).
- Actual Alembic runs core + 2 fixture tenants at session start.
- Per-test fixture wraps the test in a SAVEPOINT so side-effects roll back.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

BACKEND_DIR = Path(__file__).resolve().parent.parent
FIXTURE_TENANTS = ("test_alpha", "test_beta")


def _async_url(sync_url: str) -> str:
    # testcontainers returns e.g. "postgresql+psycopg2://..." — swap the driver.
    return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session")
def pg_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def async_database_url(pg_container: PostgresContainer) -> str:
    return _async_url(pg_container.get_connection_url())


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(async_database_url: str) -> None:
    """Run core + per-tenant migrations once for the session."""
    env = {**os.environ, "DATABASE_URL": async_database_url}

    # Core
    subprocess.run(
        ["alembic", "-x", "mode=core", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
    )

    # Insert fixture tenant rows, then migrate each tenant schema.
    import asyncio

    async def _seed_fixtures() -> None:
        engine = create_async_engine(async_database_url)
        try:
            async with engine.begin() as conn:
                for slug in FIXTURE_TENANTS:
                    await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "portal_{slug}"'))
                    await conn.execute(
                        text(
                            """
                            INSERT INTO portal_core.tenants (id, slug, name, schema_name)
                            VALUES (gen_random_uuid(), :slug, :name, :schema)
                            ON CONFLICT (slug) DO NOTHING
                            """
                        ),
                        {"slug": slug, "name": slug, "schema": f"portal_{slug}"},
                    )
        finally:
            await engine.dispose()

    asyncio.run(_seed_fixtures())

    for slug in FIXTURE_TENANTS:
        subprocess.run(
            ["alembic", "-x", f"mode=tenant:{slug}", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env=env,
            check=True,
        )


@pytest_asyncio.fixture
async def db(async_database_url: str) -> AsyncIterator[AsyncSession]:
    """Core-only session wrapped in a SAVEPOINT for rollback-per-test isolation."""
    engine = create_async_engine(async_database_url)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        await session.begin_nested()
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def tenant_session_factory(async_database_url: str):
    """Returns a helper `async def get(slug) -> AsyncSession` with translate map applied.

    Each call opens a fresh session — no SAVEPOINT here because tenant isolation
    tests need to see committed rows across sessions. Callers should clean up
    their own writes (or rely on session-scoped isolation between tests via the
    tenant schemas being partitioned by test data).
    """
    engine = create_async_engine(async_database_url)

    async def _get(slug: str) -> AsyncSession:
        session = AsyncSession(bind=engine, expire_on_commit=False)
        await session.connection(
            execution_options={"schema_translate_map": {"tenant": f"portal_{slug}"}}
        )
        return session

    yield _get
    await engine.dispose()


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()
