"""SQLAlchemy declarative bases.

Two bases so Alembic can target them independently per invocation mode:

- `CoreBase`: tables in `lens_core` schema (always resolved literally).
- `TenantBase`: per-tenant tables. Declared with `schema="tenant"` as a
  placeholder — at query time `schema_translate_map={"tenant": "lens_<slug>"}`
  rewrites this to the caller's tenant schema.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class CoreBase(DeclarativeBase):
    """Declarative base for `lens_core.*` tables."""


class TenantBase(DeclarativeBase):
    """Declarative base for per-tenant tables.

    All tables declared against this base MUST set
    `__table_args__ = {"schema": "tenant"}` so that `schema_translate_map`
    can rewrite `tenant` to the runtime `lens_<slug>` schema.
    """
