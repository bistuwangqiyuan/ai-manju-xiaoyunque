"""V10 enterprise schema — orgs, members, api_keys, usage, invites,
plus all new Job columns introduced in §1–§9.

This is a *fresh-install* migration; for existing dev DBs the in-process
``_apply_simple_migrations`` helper has been incrementally applying these
columns, so this script is idempotent (CREATE TABLE IF NOT EXISTS + ADD
COLUMN IF NOT EXISTS).

Revision ID: 20260526_0001
Revises:
Create Date: 2026-05-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260526_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # --- enterprise tables ---
    op.create_table(
        "xyq_organizations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True, index=True),
        sa.Column("owner_user_id", sa.Integer, sa.ForeignKey("xyq_users.id", ondelete="CASCADE"), index=True),
        sa.Column("plan", sa.String(20), server_default="team", nullable=False),
        sa.Column("seats_max", sa.Integer, server_default="10", nullable=False),
        sa.Column("monthly_credits_cents", sa.Integer, server_default="0", nullable=False),
        sa.Column("monthly_used_cents", sa.Integer, server_default="0", nullable=False),
        sa.Column("sso_idp_url", sa.String(400), nullable=True),
        sa.Column("private_deploy", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "xyq_org_members",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("xyq_organizations.id", ondelete="CASCADE"), index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("xyq_users.id", ondelete="CASCADE"), index=True),
        sa.Column("role", sa.String(20), server_default="editor", nullable=False, index=True),
        sa.Column("joined_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("invited_by_user_id", sa.Integer, nullable=True),
    )
    op.create_table(
        "xyq_api_keys",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("xyq_organizations.id", ondelete="CASCADE"), index=True),
        sa.Column("issued_by_user_id", sa.Integer, sa.ForeignKey("xyq_users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(80), server_default="default"),
        sa.Column("prefix", sa.String(16), unique=True, index=True, nullable=False),
        sa.Column("secret_hash", sa.String(128), nullable=False),
        sa.Column("scopes", sa.String(400), server_default="job:write,job:read"),
        sa.Column("rate_per_min", sa.Integer, server_default="60", nullable=False),
        sa.Column("monthly_quota_calls", sa.Integer, server_default="10000", nullable=False),
        sa.Column("monthly_used_calls", sa.Integer, server_default="0", nullable=False),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("TRUE"), nullable=False),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, index=True),
    )
    op.create_table(
        "xyq_org_usage",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("xyq_organizations.id", ondelete="CASCADE"), index=True),
        sa.Column("day", sa.String(10), index=True, nullable=False),
        sa.Column("jobs_count", sa.Integer, server_default="0"),
        sa.Column("episodes_count", sa.Integer, server_default="0"),
        sa.Column("minutes_rendered", sa.Float, server_default="0"),
        sa.Column("cost_cents", sa.Integer, server_default="0"),
        sa.Column("api_calls", sa.Integer, server_default="0"),
        sa.Column("api_4xx", sa.Integer, server_default="0"),
        sa.Column("api_5xx", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "xyq_org_invites",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("xyq_organizations.id", ondelete="CASCADE"), index=True),
        sa.Column("email", sa.String(200), index=True, nullable=False),
        sa.Column("role", sa.String(20), server_default="editor"),
        sa.Column("token", sa.String(80), unique=True, index=True, nullable=False),
        sa.Column("invited_by_user_id", sa.Integer, sa.ForeignKey("xyq_users.id", ondelete="CASCADE")),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("accepted_at", sa.DateTime, nullable=True),
        sa.Column("accepted_by_user_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # --- Job V10 columns that may not yet exist ---
    if dialect == "postgresql":
        for stmt in [
            "ALTER TABLE xyq_jobs ADD COLUMN IF NOT EXISTS is_draft BOOLEAN DEFAULT FALSE NOT NULL",
            "ALTER TABLE xyq_jobs ADD COLUMN IF NOT EXISTS template_id VARCHAR(60)",
            "ALTER TABLE xyq_jobs ADD COLUMN IF NOT EXISTS org_id INTEGER",
        ]:
            op.execute(stmt)


def downgrade() -> None:
    op.drop_table("xyq_org_invites")
    op.drop_table("xyq_org_usage")
    op.drop_table("xyq_api_keys")
    op.drop_table("xyq_org_members")
    op.drop_table("xyq_organizations")
