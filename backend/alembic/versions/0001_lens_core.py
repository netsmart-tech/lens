"""lens_core baseline — tenants, users, user_tenants, activities, sync_state, reports, audit_log.

Revision ID: 0001
Revises:
Create Date: 2026-04-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


SCHEMA = "lens_core"


def _phase() -> str | None:
    return context.config.attributes.get("phase")


def upgrade() -> None:
    if _phase() != "core":
        return  # tenant-phase invocations skip core-only migrations
    bind = op.get_bind()
    bind.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("schema_name", sa.String(128), nullable=False),
        sa.Column("db_url", sa.String(1024), nullable=True),
        sa.Column("color_hex", sa.String(16), nullable=True),
        sa.Column("logo_ref", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("authentik_sub", sa.String(255), nullable=True, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )

    op.create_table(
        "user_tenants",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.PrimaryKeyConstraint("user_id", "tenant_id"),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], [f"{SCHEMA}.tenants.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )
    op.create_index("ix_user_tenants_tenant_id", "user_tenants", ["tenant_id"], schema=SCHEMA)

    op.create_table(
        "activities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(1024), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("dedup_key", sa.String(512), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], [f"{SCHEMA}.tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "source", "dedup_key", name="uq_activities_dedup"),
        schema=SCHEMA,
    )
    op.create_index("ix_activities_tenant_occurred", "activities", ["tenant_id", "occurred_at"], schema=SCHEMA)
    op.create_index(
        "ix_activities_tenant_source_occurred",
        "activities",
        ["tenant_id", "source", "occurred_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "sync_state",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False, server_default="backfill"),
        sa.Column("cursor", sa.String(512), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(4096), nullable=True),
        sa.Column("backfill_complete_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "source"),
        sa.ForeignKeyConstraint(["tenant_id"], [f"{SCHEMA}.tenants.id"], ondelete="CASCADE"),
        schema=SCHEMA,
    )

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template", sa.String(128), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("author", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("markdown_ref", sa.String(1024), nullable=True),
        sa.Column("pdf_ref", sa.String(1024), nullable=True),
        sa.Column("share_slug", sa.String(128), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], [f"{SCHEMA}.tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author"], [f"{SCHEMA}.users.id"]),
        schema=SCHEMA,
    )
    op.create_index("ix_reports_tenant_period", "reports", ["tenant_id", "period_end"], schema=SCHEMA)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event", sa.String(128), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], [f"{SCHEMA}.tenants.id"], ondelete="SET NULL"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    if _phase() != "core":
        return
    op.drop_table("audit_log", schema=SCHEMA)
    op.drop_index("ix_reports_tenant_period", table_name="reports", schema=SCHEMA)
    op.drop_table("reports", schema=SCHEMA)
    op.drop_table("sync_state", schema=SCHEMA)
    op.drop_index("ix_activities_tenant_source_occurred", table_name="activities", schema=SCHEMA)
    op.drop_index("ix_activities_tenant_occurred", table_name="activities", schema=SCHEMA)
    op.drop_table("activities", schema=SCHEMA)
    op.drop_index("ix_user_tenants_tenant_id", table_name="user_tenants", schema=SCHEMA)
    op.drop_table("user_tenants", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)
    op.drop_table("tenants", schema=SCHEMA)
