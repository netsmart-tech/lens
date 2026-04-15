"""Prove `record_activity` is idempotent: same dedup_key twice = one row."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from lens.models.core.activities import Activity
from lens.models.core.tenants import Tenant
from lens.services.activities import record_activity


@pytest.mark.asyncio
async def test_record_activity_is_idempotent(db) -> None:
    # Grab an existing fixture tenant (test_alpha) so the FK is satisfied.
    t = (
        await db.execute(select(Tenant).where(Tenant.slug == "test_alpha"))
    ).scalar_one()

    dedup_key = f"ACME-1:status:open->done:{uuid.uuid4()}"
    now = datetime.now(UTC)

    for _ in range(2):
        await record_activity(
            db,
            tenant_id=t.id,
            source="jira",
            dedup_key=dedup_key,
            actor="sjensen@netsmart.tech",
            action="status_changed",
            subject="ACME-1: foo",
            occurred_at=now,
        )

    count = (
        await db.execute(
            select(func.count())
            .select_from(Activity)
            .where(Activity.tenant_id == t.id, Activity.dedup_key == dedup_key)
        )
    ).scalar_one()
    assert count == 1
