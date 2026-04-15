"""tenant-mode: jira base tables — jira_sites, jira_issues, jira_comments,
jira_changelog, jira_worklogs, jira_issue_links.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-15

Runs under `-x mode=tenant:<slug>`; env.py installs a schema_translate_map
{tenant: portal_<slug>} so `schema="tenant"` below is rewritten at execution
time to the caller's tenant schema.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


SCHEMA = "tenant"  # placeholder — rewritten by env.py's schema_translate_map


def _phase() -> str | None:
    return context.config.attributes.get("phase")


def upgrade() -> None:
    if _phase() != "tenant":
        return  # core-phase invocations skip tenant-only migrations
    op.create_table(
        "jira_sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("base_url", sa.String(512), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        schema=SCHEMA,
    )

    op.create_table(
        "jira_issues",
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("summary", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(128), nullable=True),
        sa.Column("priority", sa.String(64), nullable=True),
        sa.Column("assignee", sa.String(320), nullable=True),
        sa.Column("reporter", sa.String(320), nullable=True),
        sa.Column("issue_created", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issue_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw", postgresql.JSONB(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("site_id", "key"),
        sa.ForeignKeyConstraint(["site_id"], [f"{SCHEMA}.jira_sites.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )
    op.create_index("ix_jira_issues_assignee_status", "jira_issues", ["assignee", "status"], schema=SCHEMA)
    op.create_index("ix_jira_issues_updated", "jira_issues", ["issue_updated"], schema=SCHEMA)

    op.create_table(
        "jira_comments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_key", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("author", sa.String(320), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id", "issue_key"],
            [f"{SCHEMA}.jira_issues.site_id", f"{SCHEMA}.jira_issues.key"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_jira_comments_issue_created",
        "jira_comments",
        ["site_id", "issue_key", "created"],
        schema=SCHEMA,
    )

    op.create_table(
        "jira_changelog",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_key", sa.String(64), nullable=False),
        sa.Column("author", sa.String(320), nullable=True),
        sa.Column("field", sa.String(128), nullable=False),
        sa.Column("from_value", sa.Text(), nullable=True),
        sa.Column("to_value", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_jira_changelog_issue_changed",
        "jira_changelog",
        ["site_id", "issue_key", "changed_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "jira_worklogs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_key", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("author", sa.String(320), nullable=True),
        sa.Column("time_seconds", sa.Integer(), nullable=False),
        sa.Column("started", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("ix_jira_worklogs_issue", "jira_worklogs", ["site_id", "issue_key"], schema=SCHEMA)

    op.create_table(
        "jira_issue_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_key", sa.String(64), nullable=False),
        sa.Column("to_key", sa.String(64), nullable=False),
        sa.Column("link_type", sa.String(64), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_jira_issue_links_from", "jira_issue_links", ["site_id", "from_key"], schema=SCHEMA
    )


def downgrade() -> None:
    if _phase() != "tenant":
        return
    op.drop_index("ix_jira_issue_links_from", table_name="jira_issue_links", schema=SCHEMA)
    op.drop_table("jira_issue_links", schema=SCHEMA)
    op.drop_index("ix_jira_worklogs_issue", table_name="jira_worklogs", schema=SCHEMA)
    op.drop_table("jira_worklogs", schema=SCHEMA)
    op.drop_index("ix_jira_changelog_issue_changed", table_name="jira_changelog", schema=SCHEMA)
    op.drop_table("jira_changelog", schema=SCHEMA)
    op.drop_index("ix_jira_comments_issue_created", table_name="jira_comments", schema=SCHEMA)
    op.drop_table("jira_comments", schema=SCHEMA)
    op.drop_index("ix_jira_issues_updated", table_name="jira_issues", schema=SCHEMA)
    op.drop_index("ix_jira_issues_assignee_status", table_name="jira_issues", schema=SCHEMA)
    op.drop_table("jira_issues", schema=SCHEMA)
    op.drop_table("jira_sites", schema=SCHEMA)
