"""Critical: prove that `schema_translate_map` actually isolates tenants.

Insert distinct jira_issues rows into `lens_test_alpha` and `lens_test_beta`,
then query each through a tenant-scoped session and assert no bleed-through.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from lens.models.tenant.jira_issues import JiraIssue
from lens.models.tenant.jira_sites import JiraSite


@pytest.mark.asyncio
async def test_tenant_isolation(tenant_session_factory) -> None:
    alpha_site = uuid.uuid4()
    beta_site = uuid.uuid4()

    # Insert into alpha — flush site before adding issue so the FK parent
    # row commits first (JiraIssue lacks an explicit ORM relationship, so
    # SQLAlchemy won't auto-order inserts across them).
    alpha = await tenant_session_factory("test_alpha")
    try:
        alpha.add(JiraSite(id=alpha_site, base_url="https://alpha.atlassian.net", display_name="alpha"))
        await alpha.flush()
        alpha.add(
            JiraIssue(
                site_id=alpha_site,
                key="ALPHA-1",
                summary="alpha ticket",
                assignee="alpha@example.com",
            )
        )
        await alpha.commit()
    finally:
        await alpha.close()

    # Insert into beta
    beta = await tenant_session_factory("test_beta")
    try:
        beta.add(JiraSite(id=beta_site, base_url="https://beta.atlassian.net", display_name="beta"))
        await beta.flush()
        beta.add(
            JiraIssue(
                site_id=beta_site,
                key="BETA-1",
                summary="beta ticket",
                assignee="beta@example.com",
            )
        )
        await beta.commit()
    finally:
        await beta.close()

    # Query alpha — should see only ALPHA-*
    alpha = await tenant_session_factory("test_alpha")
    try:
        rows = (await alpha.execute(select(JiraIssue))).scalars().all()
        keys = {r.key for r in rows}
        assert "ALPHA-1" in keys
        assert "BETA-1" not in keys, f"tenant bleed: found BETA rows in alpha schema: {keys}"
    finally:
        await alpha.close()

    # Query beta — should see only BETA-*
    beta = await tenant_session_factory("test_beta")
    try:
        rows = (await beta.execute(select(JiraIssue))).scalars().all()
        keys = {r.key for r in rows}
        assert "BETA-1" in keys
        assert "ALPHA-1" not in keys, f"tenant bleed: found ALPHA rows in beta schema: {keys}"
    finally:
        await beta.close()
