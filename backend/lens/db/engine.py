"""Async engine + session factory. Lifespan owns startup/shutdown."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

from lens.config import settings

# Shared default engine for all tenants whose `tenants.db_url` is NULL.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[_AsyncSession] | None = None

# Per-tenant engine cache for Phase 5 physical-isolation escape hatch.
# Key: db_url string. Value: AsyncEngine.
_tenant_engine_cache: dict[str, AsyncEngine] = {}


def _build_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
    )


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _build_engine(settings.database_url)
    return _engine


def get_session_factory() -> async_sessionmaker[_AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


def get_tenant_engine(db_url: str | None) -> AsyncEngine:
    """Return the engine for a tenant. Uses the default engine if `db_url` is None/empty.

    TODO(Phase 5): per-tenant engine cache implemented below; verify pool sizing
    when the first physically-isolated tenant comes online.
    """
    if not db_url:
        return get_engine()
    eng = _tenant_engine_cache.get(db_url)
    if eng is None:
        eng = _build_engine(db_url)
        _tenant_engine_cache[db_url] = eng
    return eng


async def shutdown_engines() -> None:
    """Dispose the default engine + any cached per-tenant engines."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    for eng in _tenant_engine_cache.values():
        await eng.dispose()
    _tenant_engine_cache.clear()
    _engine = None
    _session_factory = None
