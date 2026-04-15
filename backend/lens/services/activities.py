"""`record_activity` — idempotent INSERT to `portal_core.activities`.

Per Teo §9: use a single `dedup_key` column + `ON CONFLICT (tenant_id, source,
dedup_key) DO NOTHING` for idempotent re-sync.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lens.models.core.activities import Activity


async def record_activity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    source: str,
    dedup_key: str,
    actor: str,
    action: str,
    subject: str,
    occurred_at: datetime,
    metadata: dict[str, Any] | None = None,
) -> None:
    stmt = (
        pg_insert(Activity)
        .values(
            tenant_id=tenant_id,
            source=source,
            dedup_key=dedup_key,
            actor=actor,
            action=action,
            subject=subject,
            occurred_at=occurred_at,
            metadata_=metadata,
        )
        .on_conflict_do_nothing(constraint="uq_activities_dedup")
    )
    await session.execute(stmt)
