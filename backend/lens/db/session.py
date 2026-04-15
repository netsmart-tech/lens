"""Async session factories + the default (core-only) DB dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from lens.db.engine import get_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a core-only AsyncSession.

    Use this for endpoints that only read/write `lens_core.*` (auth, tenant
    list, etc). For per-tenant endpoints, use `resolve_tenant` from db.tenant.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
