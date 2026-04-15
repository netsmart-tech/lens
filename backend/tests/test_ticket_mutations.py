"""Happy-path coverage for the ticket-mutation endpoints.

- POST /api/{tenant}/tickets/{key}/comments     → wraps plain text in ADF, posts to Jira, dual-writes locally.
- GET  /api/{tenant}/tickets/{key}/transitions  → reshapes Jira's transition list.
- POST /api/{tenant}/tickets/{key}/transitions  → applies transition + re-syncs the issue.

Outbound Jira calls are short-circuited by patching `JiraClient`'s private
`_get` / `_post` / `_post_no_content` coroutines with fixture responses —
same approach as the rest of the suite (no real network from tests).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from lens.auth.session import encode_session
from lens.config import settings
from lens.models.core.users import User
from lens.models.tenant.jira_comments import JiraComment
from lens.models.tenant.jira_issues import JiraIssue
from lens.models.tenant.jira_sites import JiraSite
from lens.services import jira as jira_service

TENANT = "test_alpha"
TENANT_SCHEMA = f"lens_{TENANT}"
ISSUE_KEY = "MUTATE-1"


@pytest.fixture(autouse=True)
def _point_settings_at_testdb(async_database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the default engine factory at the testcontainers DB.

    The app's `lens.db.engine` module lazily builds its engine from
    `settings.database_url`, so patching the setting before the first call
    (and resetting the module-level cache) is enough to steer production-style
    code paths (`get_db`, `resolve_tenant`) at the test database.
    """
    from lens.db import engine as engine_mod

    monkeypatch.setattr(settings, "database_url", async_database_url)
    monkeypatch.setattr(engine_mod, "_engine", None)
    monkeypatch.setattr(engine_mod, "_session_factory", None)
    monkeypatch.setattr(engine_mod, "_tenant_engine_cache", {})


@pytest.fixture(autouse=True)
def _stub_jira_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make `resolve_jira_config` return canned creds without touching env vars."""
    from lens.routers import tickets as tickets_router
    from lens.services import jira_tenant

    def _fake(slug: str) -> tuple[str, str]:
        return ("https://fake-jira.atlassian.test", "Basic dGVzdDp0ZXN0")

    monkeypatch.setattr(jira_tenant, "resolve_jira_config", _fake)
    # Router imported the name at module load, so patch it there too.
    monkeypatch.setattr(tickets_router, "resolve_jira_config", _fake)


@pytest.fixture
async def staff_user(async_database_url: str) -> User:
    """Find-or-create a staff user so `resolve_tenant`'s staff bypass kicks in.

    Uses a dedicated connection rather than the `db` SAVEPOINT fixture because
    the HTTP call under test opens its own session from the same engine; a
    nested-savepoint commit wouldn't be visible there.
    """
    engine = create_async_engine(async_database_url)
    try:
        async with AsyncSession(bind=engine, expire_on_commit=False) as s:
            existing = (
                await s.execute(select(User).where(User.email == "test-teo@netsmart.tech"))
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            u = User(
                email="test-teo@netsmart.tech",
                display_name="Teo Test",
                is_staff=True,
            )
            s.add(u)
            await s.commit()
            await s.refresh(u)
            return u
    finally:
        await engine.dispose()


@pytest.fixture
async def seed_issue(async_database_url: str, staff_user: User) -> dict[str, Any]:
    """Seed a jira_sites + jira_issues row in the tenant schema for ISSUE_KEY.

    Idempotent: `jira_sites.base_url` is unique, so tests that re-run (or
    share the site across multiple tests in one session) must find-or-create
    rather than always insert.
    """
    engine = create_async_engine(async_database_url)
    base_url = "https://fake-jira.atlassian.test"
    try:
        async with AsyncSession(bind=engine, expire_on_commit=False) as s:
            await s.connection(
                execution_options={"schema_translate_map": {"tenant": TENANT_SCHEMA}}
            )
            existing_site = (
                await s.execute(select(JiraSite).where(JiraSite.base_url == base_url))
            ).scalar_one_or_none()
            if existing_site is None:
                site = JiraSite(id=uuid.uuid4(), base_url=base_url, display_name="fake")
                s.add(site)
                await s.flush()
                site_id = site.id
            else:
                site_id = existing_site.id

            existing_issue = (
                await s.execute(select(JiraIssue).where(JiraIssue.key == ISSUE_KEY))
            ).scalar_one_or_none()
            if existing_issue is None:
                s.add(
                    JiraIssue(
                        site_id=site_id,
                        key=ISSUE_KEY,
                        summary="Mutation target",
                        status="To Do",
                        assignee="teo@netsmart.tech",
                        raw={"key": ISSUE_KEY, "fields": {"summary": "Mutation target"}},
                    )
                )
            else:
                existing_issue.status = "To Do"
                existing_issue.priority = None
                existing_issue.raw = {"key": ISSUE_KEY, "fields": {"summary": "Mutation target"}}
            await s.commit()
    finally:
        await engine.dispose()
    return {"site_id": site_id}


@pytest.fixture
async def http_client(staff_user: User):
    """ASGI httpx client with a signed session cookie for `staff_user`."""
    from lens.main import app

    transport = httpx.ASGITransport(app=app)
    token = encode_session({"user_id": str(staff_user.id)})
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.session_cookie_name: token},
    ) as client:
        yield client


# ---- helpers ---------------------------------------------------------------


def _patch_jira_calls(
    monkeypatch: pytest.MonkeyPatch,
    *,
    get_map: dict[str, Any] | None = None,
    post_map: dict[str, Any] | None = None,
    post_no_content_paths: set[str] | None = None,
) -> None:
    """Replace JiraClient._get / _post / _post_no_content with dict-driven stubs."""
    get_map = get_map or {}
    post_map = post_map or {}
    post_no_content_paths = post_no_content_paths or set()

    async def fake_get(self, path: str, params: dict | None = None) -> dict:
        if path not in get_map:
            raise AssertionError(f"unexpected Jira GET {path}")
        return get_map[path]

    async def fake_post(self, path: str, json_body: dict) -> dict:
        if path not in post_map:
            raise AssertionError(f"unexpected Jira POST {path}")
        return post_map[path]

    async def fake_post_nc(self, path: str, json_body: dict) -> None:
        if path not in post_no_content_paths:
            raise AssertionError(f"unexpected Jira POST(no-content) {path}")

    monkeypatch.setattr(jira_service.JiraClient, "_get", fake_get)
    monkeypatch.setattr(jira_service.JiraClient, "_post", fake_post)
    monkeypatch.setattr(jira_service.JiraClient, "_post_no_content", fake_post_nc)


# ---- tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_comment_posts_adf_and_dual_writes(
    http_client: httpx.AsyncClient,
    seed_issue: dict[str, Any],
    async_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_post(self, path: str, json_body: dict) -> dict:
        captured["path"] = path
        captured["body"] = json_body
        return {
            "id": "10001",
            "author": {"emailAddress": "teo@netsmart.tech", "displayName": "Teo"},
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "hello"}]},
                    {"type": "paragraph", "content": [{"type": "text", "text": "world"}]},
                ],
            },
            "created": "2026-04-15T12:00:00.000+0000",
        }

    monkeypatch.setattr(jira_service.JiraClient, "_post", fake_post)

    resp = await http_client.post(
        f"/api/{TENANT}/tickets/{ISSUE_KEY}/comments",
        json={"body": "hello\n\nworld"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == 10001
    assert body["author"] == "teo@netsmart.tech"
    assert "hello" in body["body"] and "world" in body["body"]

    # Jira payload shape: {body: {type: doc, ...}} with 2 paragraphs.
    assert captured["path"] == f"/rest/api/3/issue/{ISSUE_KEY}/comment"
    doc = captured["body"]["body"]
    assert doc["type"] == "doc"
    assert len(doc["content"]) == 2
    assert doc["content"][0]["content"][0]["text"] == "hello"
    assert doc["content"][1]["content"][0]["text"] == "world"

    # Dual-write: row landed in tenant.jira_comments.
    engine = create_async_engine(async_database_url)
    try:
        async with AsyncSession(bind=engine, expire_on_commit=False) as s:
            await s.connection(
                execution_options={"schema_translate_map": {"tenant": TENANT_SCHEMA}}
            )
            rows = (
                await s.execute(
                    select(JiraComment).where(JiraComment.issue_key == ISSUE_KEY)
                )
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].external_id == "10001"
            assert rows[0].author == "teo@netsmart.tech"
            # Cleanup so repeat runs stay idempotent.
            for r in rows:
                await s.delete(r)
            await s.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_list_transitions_reshapes_jira_response(
    http_client: httpx.AsyncClient,
    seed_issue: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_jira_calls(
        monkeypatch,
        get_map={
            f"/rest/api/3/issue/{ISSUE_KEY}/transitions": {
                "transitions": [
                    {"id": "11", "name": "In Progress", "to": {"name": "In Progress"}},
                    {"id": "21", "name": "Done", "to": {"name": "Done"}},
                ]
            }
        },
    )

    resp = await http_client.get(f"/api/{TENANT}/tickets/{ISSUE_KEY}/transitions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "transitions": [
            {"id": "11", "name": "In Progress", "to_status": "In Progress"},
            {"id": "21", "name": "Done", "to_status": "Done"},
        ]
    }


@pytest.mark.asyncio
async def test_apply_transition_resyncs_issue_status(
    http_client: httpx.AsyncClient,
    seed_issue: dict[str, Any],
    async_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Jira: 204 on transition, then /issue/{key} returns fresh status.
    refreshed_payload = {
        "key": ISSUE_KEY,
        "fields": {
            "summary": "Mutation target",
            "status": {"name": "Done"},
            "priority": {"name": "Medium"},
            "assignee": {"emailAddress": "teo@netsmart.tech"},
            "reporter": {"emailAddress": "steve@netsmart.tech"},
            "created": "2026-04-01T10:00:00.000+0000",
            "updated": "2026-04-15T13:00:00.000+0000",
            "description": None,
        },
    }
    _patch_jira_calls(
        monkeypatch,
        get_map={f"/rest/api/3/issue/{ISSUE_KEY}": refreshed_payload},
        post_no_content_paths={f"/rest/api/3/issue/{ISSUE_KEY}/transitions"},
    )

    resp = await http_client.post(
        f"/api/{TENANT}/tickets/{ISSUE_KEY}/transitions",
        json={"transition_id": "21"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == ISSUE_KEY
    assert body["status"] == "Done"
    assert body["priority"] == "Medium"

    # Verify the row was upserted in the tenant schema.
    engine = create_async_engine(async_database_url)
    try:
        async with AsyncSession(bind=engine, expire_on_commit=False) as s:
            await s.connection(
                execution_options={"schema_translate_map": {"tenant": TENANT_SCHEMA}}
            )
            row = (
                await s.execute(select(JiraIssue).where(JiraIssue.key == ISSUE_KEY))
            ).scalar_one()
            assert row.status == "Done"
            # Reset for rerunnability.
            row.status = "To Do"
            row.priority = None
            row.raw = {"key": ISSUE_KEY, "fields": {"summary": "Mutation target"}}
            row.issue_updated = None
            await s.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_comment_validates_non_empty_body(
    http_client: httpx.AsyncClient,
    seed_issue: dict[str, Any],
) -> None:
    resp = await http_client.post(
        f"/api/{TENANT}/tickets/{ISSUE_KEY}/comments",
        json={"body": "   "},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_comment_404_when_ticket_missing(
    http_client: httpx.AsyncClient,
    staff_user: User,
) -> None:
    resp = await http_client.post(
        f"/api/{TENANT}/tickets/DOES-NOT-EXIST/comments",
        json={"body": "hi"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_plain_text_to_adf_helper() -> None:
    from lens.services.jira import plain_text_to_adf

    doc = plain_text_to_adf("one\n\ntwo\nwith soft break\n\nthree")
    assert doc["type"] == "doc" and doc["version"] == 1
    assert len(doc["content"]) == 3
    assert doc["content"][1]["content"][0]["text"] == "two\nwith soft break"

    # Blank-only paragraphs get dropped.
    doc2 = plain_text_to_adf("a\n\n   \n\nb")
    texts = [p["content"][0]["text"] for p in doc2["content"]]
    assert texts == ["a", "b"]


# Hint to silence pytest's unused-import warnings when running only a subset.
_ = datetime(2026, 1, 1, tzinfo=UTC)
