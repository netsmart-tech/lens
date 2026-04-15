"""Sync envelope helper — wraps list responses in the DESIGN §3.7 shape.

State taxonomy (Zara frontend drives off of this):
  never-synced         — no sync_state row for (tenant, source)
  syncing-first-pass   — sync_state.mode == 'backfill'
  failed               — sync_state.last_error is set
  stale                — last_run_at > settings.stale_threshold_s ago
  synced-but-empty     — items == 0 (and we've synced at least once)
  fresh                — default happy path
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lens.config import settings
from lens.models.core.sync_state import SyncState
from lens.schemas.sync import SyncBlock, SyncStateLiteral


def _compute_state(
    sync_state: SyncState | None,
    items: Sequence[Any],
    now: datetime,
) -> SyncStateLiteral:
    if sync_state is None:
        return "never-synced"
    if sync_state.last_error:
        return "failed"
    if sync_state.mode == "backfill" and sync_state.backfill_complete_at is None:
        return "syncing-first-pass"
    if sync_state.last_run_at is None:
        # sync_state row exists but has never successfully run
        return "never-synced"
    age_s = (now - sync_state.last_run_at).total_seconds()
    if age_s > settings.stale_threshold_s:
        return "stale"
    if len(items) == 0:
        return "synced-but-empty"
    return "fresh"


async def with_sync_envelope(
    session: AsyncSession,
    tenant_id,
    source: str,
    items: Sequence[Any],
) -> dict:
    """Return `{items, sync: {...}}`. Callers pass already-serialized items."""
    stmt = select(SyncState).where(
        SyncState.tenant_id == tenant_id, SyncState.source == source
    )
    sync_state = (await session.execute(stmt)).scalar_one_or_none()

    now = datetime.now(UTC)
    state = _compute_state(sync_state, items, now)

    block = SyncBlock(
        state=state,
        last_run_at=sync_state.last_run_at if sync_state else None,
        last_cursor_at=sync_state.last_success_at if sync_state else None,
        last_error=sync_state.last_error if sync_state else None,
        progress=None,  # TODO(Phase 2): emit {pct} during backfill
    )
    return {"items": list(items), "sync": block.model_dump(mode="json")}
